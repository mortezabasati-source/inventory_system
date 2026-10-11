"""Closed set of deterministic analysis operations over an immutable snapshot."""
import json
import math
from collections import deque
from datetime import date

import pandas as pd

from modules.inventory_engine import calculate_current_stock
from modules.product_cost import calculate_product_cost_and_margin


class AnalysisError(ValueError):
    pass


SPECS = {
    "current_stock": ("Aktuellt lagersaldo, inte historiskt saldo", {"item_id", "supplier", "limit"}, ()),
    "inbound": ("Inleveranser i basenheter", {"item_id", "supplier", "start_date", "end_date", "group_by", "limit"}, ("item", "supplier", "day", "total")),
    "production": ("Producerade antal, inte försäljning", {"product_id", "start_date", "end_date", "group_by", "limit"}, ("product", "day", "total")),
    "consumption": ("Materialförbrukning enligt nuvarande BOM och produktionslogg", {"item_id", "product_id", "start_date", "end_date", "group_by", "limit"}, ("item", "product", "day", "total")),
    "deviations": ("Stickprovsavvikelser i basenheter", {"item_id", "start_date", "end_date", "group_by", "limit"}, ("item", "day", "total")),
    "margins": ("Nuvarande kalkylerad produktkostnad och marginal, inte faktisk försäljningsvinst", {"product_id", "limit"}, ()),
}


def declarations():
    functions = []
    for name, (description, fields, groups) in SPECS.items():
        properties = {}
        for field in sorted(fields):
            spec = {"type": "integer" if field == "limit" else "string"}
            if field in ("start_date", "end_date"):
                spec["description"] = "Inclusive date YYYY-MM-DD"
            if field == "group_by":
                spec["enum"] = list(groups)
            if field == "limit":
                spec["description"] = "Maximum returned rows, 1 to 100; default 100"
            properties[field] = spec
        functions.append({"name": name, "description": description,
                          "parameters": {"type": "object", "properties": properties}})
    return functions


def validate(name, args):
    if name not in SPECS or not isinstance(args, dict):
        raise AnalysisError("Okänt analysverktyg.")
    if set(args) - SPECS[name][1]:
        raise AnalysisError("Otillåtna parametrar.")
    for key, value in args.items():
        if key == "limit":
            if type(value) is not int or not 1 <= value <= 100:
                raise AnalysisError("limit måste vara ett heltal mellan 1 och 100.")
        elif not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise AnalysisError("Ogiltigt parametervärde.")
        if key in ("start_date", "end_date"):
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            except ValueError:
                raise AnalysisError("Datum måste anges som YYYY-MM-DD.") from None
    if args.get("start_date", "") > args.get("end_date", "9999-12-31"):
        raise AnalysisError("Startdatum ligger efter slutdatum.")
    if "group_by" in args and args["group_by"] not in SPECS[name][2]:
        raise AnalysisError("Ogiltig gruppering.")


def require(frame, columns, source):
    if not frame.empty and not set(columns).issubset(frame.columns):
        raise AnalysisError(f"Obligatoriska kolumner saknas i {source}.")
    if frame.empty:
        return frame.reindex(columns=list(dict.fromkeys([*frame.columns, *columns])))
    return frame


def numeric(frame, columns, source):
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not values.map(lambda x: math.isfinite(float(x))).all():
            raise AnalysisError(f"Ogiltiga tal i {source}: {column}.")
        frame[column] = values


def apply_blank_default(frame, column, default):
    """Use an established app default only for empty cells, never invalid text."""
    values = frame[column]
    blank = values.isna() | values.astype(str).str.strip().eq("")
    count = int(blank.sum())
    if count:
        frame[column] = values.astype(object).mask(blank, default)
    return count


def check_bom_cycles(frame):
    """Topological check also protects stock/consumption tools without recursion."""
    nodes = set(frame["Produkt_id"].astype(str))
    graph = {node: set() for node in nodes}
    for parent, child in zip(frame["Produkt_id"].astype(str), frame["SI"].astype(str)):
        if child in nodes:
            graph[parent].add(child)
    incoming = dict.fromkeys(nodes, 0)
    for children in graph.values():
        for child in children:
            incoming[child] += 1
    ready = deque(node for node, count in incoming.items() if count == 0)
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for child in graph[node]:
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if visited != len(nodes):
        raise AnalysisError("Cykel i BOM.")


def filtered(frame, args, id_column=None):
    for key, column in (("item_id", id_column or "SI_Code"), ("product_id", "Product_ID"), ("supplier", "Leverantör")):
        if key in args:
            if column not in frame:
                raise AnalysisError(f"Kolumn saknas för filter: {key}.")
            frame = frame[frame[column].astype(str).str.strip() == args[key].strip()]
    if "Datum" in frame:
        dates = pd.to_datetime(frame["Datum"], errors="coerce")
        if dates.isna().any():
            raise AnalysisError("Ogiltiga datum i loggen.")
        frame = frame.copy()
        frame["Datum"] = dates.dt.strftime("%Y-%m-%d")
        for key, operator in (("start_date", "ge"), ("end_date", "le")):
            if key in args:
                frame = frame[getattr(frame["Datum"], operator)(args[key])]
    return frame


class AnalysisTools:
    def __init__(self, snapshot):
        self.frames = {name: frame.copy(deep=True) for name, frame in snapshot["frames"].items()}
        self.fetched_at = snapshot["fetched_at"]

    def execute(self, name, args):
        validate(name, args)
        f = {key: value.copy(deep=True) for key, value in self.frames.items()}
        sources = []
        warnings = []

        def table(source, columns, numbers=()):
            if source not in f:
                raise AnalysisError(f"Datakälla saknas: {source}.")
            result = require(f[source], columns, source)
            if source == "BOM" and "Förbrukning" in numbers:
                count = apply_blank_default(result, "Förbrukning", 0)
                if count:
                    warnings.append(f"{count} tomma Förbrukning-värden i BOM tolkas som 0 förbrukning, enligt appens befintliga beräkning. Dessa receptdelar saknar angiven mängd; kontrollera receptet vid behov. Källdata ändras inte.")
            numeric(result, numbers, source)
            if source == "BOM":
                result["Produkt_id"] = result["Produkt_id"].astype(str).str.strip()
                result["SI"] = result["SI"].astype(str).str.strip()
                check_bom_cycles(result)
            sources.append(source)
            return result

        def materials(*, stock=False, cost=False):
            columns = ["Sl", "Insatsvara", "Typ"]
            numbers = []
            if stock:
                columns.extend(["Vikt/Pcs", "Antal", "Leverantör"])
                numbers.extend(["Vikt/Pcs", "Antal"])
            if cost:
                columns.extend(["Vikt/Pcs", "Pris (Kr)"])
                numbers.extend(["Vikt/Pcs", "Pris (Kr)"])
            frame = table("Insatsvara", columns)
            if stock:
                count = apply_blank_default(frame, "Antal", 0)
                if count:
                    # Match the existing stock engine's opening-balance default
                    # on this snapshot only. Nonempty invalid values still fail.
                    warnings.append(f"{count} tomma Antal-värden i Insatsvara tolkas som 0 i ingående saldo, enligt appens befintliga beräkning. Källdata ändras inte.")
            numeric(frame, numbers, "Insatsvara")
            frame["Sl"] = frame["Sl"].astype(str).str.strip()
            if frame["Sl"].duplicated().any():
                raise AnalysisError("Dubbla artikel-ID i Insatsvara.")
            return frame

        def attach_units(frame, insats):
            # BOM/log sheets may already contain Insatsvara or Typ. Always use
            # authoritative material metadata, avoiding pandas' _x/_y suffixes.
            frame = frame.drop(columns=["Sl", "Insatsvara", "Typ", "Unit"], errors="ignore").copy()
            frame["SI_Code"] = frame["SI_Code"].astype(str).str.strip()
            result = frame.merge(insats[["Sl", "Insatsvara", "Typ"]], left_on="SI_Code", right_on="Sl", how="left", validate="many_to_one")
            if result["Typ"].isna().any():
                raise AnalysisError("Artikel saknas i Insatsvara; enhet kan inte fastställas.")
            return result.rename(columns={"Typ": "Unit"})

        if name == "current_stock":
            insats = materials(stock=True)
            bom = table("BOM", ["Produkt_id", "SI", "Förbrukning"], ["Förbrukning"])
            inbound = table("Inbound_Log", ["SI_Code", "Total_Base_Qty"], ["Total_Base_Qty"])
            production = table("Production_Log", ["Product_ID", "Quantity_Produced"], ["Quantity_Produced"])
            deviations = table("Stickprov_Log", ["SI_Code", "Deviation"], ["Deviation"])
            result = calculate_current_stock(insats, bom, inbound, production, deviations)
            result = filtered(result, args, "Sl")
            if "Total_Deviation" not in result:
                result["Total_Deviation"] = 0.0
            result = result.reindex(columns=["Sl", "Insatsvara", "Typ", "Leverantör", "Initial_Base_Stock", "Total_Inbound", "Total_Consumed", "Total_Deviation", "Current_Stock"])
            result = result.sort_values("Current_Stock", kind="stable")
            warnings.append("Aktuellt saldo använder appens befintliga beräkning och nuvarande BOM; historiskt saldo stöds inte.")
            warnings.append("Raderna är sorterade efter aktuellt saldo, stigande.")
        elif name == "margins":
            insats = materials(cost=True)
            products = table("Products", ["Produkt_id", "Produkt_namn", "Utpris"], ["Utpris"])
            products["Produkt_id"] = products["Produkt_id"].astype(str).str.strip()
            bom = table("BOM", ["Produkt_id", "SI", "Förbrukning"], ["Förbrukning"])
            known = set(insats["Sl"]) | set(bom["Produkt_id"].astype(str))
            unknown = ~bom["SI"].isin(known)
            if (unknown & bom["Förbrukning"].ne(0)).any():
                raise AnalysisError("BOM refererar till okända artiklar med förbrukning som inte är noll; deras kostnad kan inte fastställas.")
            ignored = int((unknown & bom["Förbrukning"].eq(0)).sum())
            if ignored:
                warnings.append(f"{ignored} BOM-rader har tomt eller okänt artikel-ID och 0 förbrukning. De bidrar med 0 till kostnaden och hindrar inte marginalberäkningen. Källdata ändras inte.")
            if set(products["Produkt_id"].astype(str)) - known:
                raise AnalysisError("BOM eller kostnadsunderlag saknas för en produkt.")
            consumed_ids = set(bom.loc[bom["Förbrukning"].ne(0), "SI"])
            consumed_materials = insats[insats["Sl"].isin(consumed_ids)]
            if (consumed_materials["Vikt/Pcs"] <= 0).any():
                raise AnalysisError("Vikt/Pcs måste vara positiv för kostnadsberäkning.")
            try:
                result = calculate_product_cost_and_margin(products, bom, insats)
            except (ValueError, RecursionError):
                raise AnalysisError("Cykel eller ogiltig struktur i BOM.") from None
            result = filtered(result.rename(columns={"Produkt_id": "Product_ID"}), args)
            result = result.reindex(columns=["Product_ID", "Produkt_namn", "Utpris", "Kostpris", "Vinstmarginal (%)"])
            result = result.sort_values("Vinstmarginal (%)", kind="stable")
            warnings.append("Kalkylerad marginal i SEK med nuvarande priser och BOM; inte faktisk försäljningsvinst.")
            warnings.append("Raderna är sorterade efter kalkylerad marginal, stigande.")
        else:
            insats = materials() if name != "production" else None
            if name == "production":
                result = table("Production_Log", ["Datum", "Product_ID", "Quantity_Produced"], ["Quantity_Produced"])
                result = filtered(result, args)
                result["Unit"] = "st"
                quantity, default_group = "Quantity_Produced", "product"
            elif name == "consumption":
                production = table("Production_Log", ["Datum", "Product_ID", "Quantity_Produced"], ["Quantity_Produced"])
                # Only product and date filters apply before the BOM join.
                production = filtered(production, {k: v for k, v in args.items() if k != "item_id"})
                bom = table("BOM", ["Produkt_id", "SI", "Förbrukning"], ["Förbrukning"])
                production["Product_ID"] = production["Product_ID"].astype(str)
                bom["Produkt_id"] = bom["Produkt_id"].astype(str)
                if set(production["Product_ID"]) - set(bom["Produkt_id"]):
                    raise AnalysisError("BOM saknas för producerad produkt.")
                result = production.merge(bom, left_on="Product_ID", right_on="Produkt_id")
                result["Consumed_Qty"] = result["Quantity_Produced"] * result["Förbrukning"]
                result = result.rename(columns={"SI": "SI_Code"})
                quantity, default_group = "Consumed_Qty", "item"
                warnings.append("Förbrukning följer appens direkta BOM-rader och nuvarande recept; historiska recept finns inte.")
            elif name == "inbound":
                columns = ["Datum", "SI_Code", "Total_Base_Qty"]
                if "supplier" in args or args.get("group_by") == "supplier":
                    columns.append("Leverantör")
                result = table("Inbound_Log", columns, ["Total_Base_Qty"])
                quantity, default_group = "Total_Base_Qty", "item"
            else:
                result = table("Stickprov_Log", ["Datum", "SI_Code", "Deviation"], ["Deviation"])
                quantity, default_group = "Deviation", "item"
            if name != "production":
                result = attach_units(result, insats)
                result = filtered(result, args)
            group = args.get("group_by", default_group)
            column = {"item": "SI_Code", "product": "Product_ID", "supplier": "Leverantör", "day": "Datum", "total": "Unit"}[group]
            groups = ["Unit"] if group == "total" else [column, "Unit"]
            if group == "item":
                groups.insert(1, "Insatsvara")
            result = result.groupby(groups, dropna=False)[quantity].sum().reset_index()

        total_rows = len(result)
        limit = args.get("limit", 100)
        result = result.head(limit)
        if total_rows > limit:
            warnings.append(f"Resultatet är begränsat till {limit} av {total_rows} rader.")
        if result.empty:
            warnings.append("Inga matchande data.")
        return {"tool": name, "filters": args, "sources": list(dict.fromkeys(sources)),
                "fetched_at": self.fetched_at, "total_rows": total_rows, "truncated": total_rows > limit,
                "warnings": warnings, "rows": json.loads(result.to_json(orient="records", date_format="iso"))}
