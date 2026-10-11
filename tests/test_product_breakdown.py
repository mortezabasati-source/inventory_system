"""Ingredient pricing must agree with recursive product margins."""
import unittest
import pandas as pd
from modules.product_cost import calculate_ingredient_breakdown, calculate_product_cost_and_margin


class BreakdownTests(unittest.TestCase):
    def test_units_nested_recipes_and_numeric_material_ids(self):
        products = pd.DataFrame([
            {'Produkt_id': 'P1', 'Produkt_namn': 'Bread', 'Utpris': 100},
            {'Produkt_id': 'P2', 'Produkt_namn': 'Dough', 'Utpris': 0},
        ])
        materials = pd.DataFrame([
            {'Sl': 501, 'Insatsvara': 'Flour', 'Typ': 'g', 'Vikt/Pcs': 5000, 'Pris (Kr)': 40, 'Pris_Enhet': 'kg'},
            {'Sl': 502, 'Insatsvara': 'Spice', 'Typ': 'g', 'Vikt/Pcs': 50, 'Pris (Kr)': 2, 'Pris_Enhet': 'g'},
            {'Sl': 503, 'Insatsvara': 'Box', 'Typ': 'st', 'Vikt/Pcs': 10, 'Pris (Kr)': 20, 'Pris_Enhet': 'pkg'},
            {'Sl': 504, 'Insatsvara': 'Salt', 'Typ': 'g', 'Vikt/Pcs': 0, 'Pris (Kr)': 20, 'Pris_Enhet': 'pkg'},
        ])
        bom = pd.DataFrame([
            {'Produkt_id': 'P2', 'SI': 501, 'Förbrukning': 100},
            {'Produkt_id': 'P1', 'SI': 'P2', 'Förbrukning': 2},
            {'Produkt_id': 'P1', 'SI': 502, 'Förbrukning': 3},
            {'Produkt_id': 'P1', 'SI': 503, 'Förbrukning': 1},
            {'Produkt_id': 'P1', 'SI': 504, 'Förbrukning': 1},
        ])
        original = bom.copy(deep=True)
        result = calculate_ingredient_breakdown('P1', products, bom, materials)
        self.assertEqual(result['Total Kostnad'].tolist(), [8, 6, 2, 0])
        self.assertEqual(result['Ingrediens'].tolist(), ['Dough', 'Spice', 'Box', 'Salt'])
        margin = calculate_product_cost_and_margin(products, bom, materials)
        self.assertEqual(result['Total Kostnad'].sum(), margin.iloc[0]['Kostpris'])
        pd.testing.assert_frame_equal(bom, original)
        self.assertTrue(calculate_ingredient_breakdown('missing', products, bom, materials).empty)
