export default function (component) {
    const {data, parentElement} = component;
    // Preserve actual user activity across Streamlit reruns and page changes.
    const state = window.__smartlagerIdleState ??= {
        lastActivity: Date.now(),
        dirtyFields: new Map(),
        submittedForms: new Set(),
        cleanup: null,
    };
    state.cleanup?.();
    // A render after a submitted form means Python has processed that submission.
    // Baskets are protected separately by hasPendingChanges.
    for (const field of state.dirtyFields.keys()) {
        if (state.submittedForms.has(field.closest('[data-testid="stForm"]'))) {
            state.dirtyFields.delete(field);
        }
    }
    state.submittedForms.clear();

    const status = parentElement.querySelector("[role='status']");
    const timeoutMs = data.timeoutMs;
    let stopped = false;

    function hasDirtyFields() {
        // Submitted clear_on_submit forms and removed widgets no longer need protection.
        for (const [field, editedValue] of state.dirtyFields) {
            if (!field.isConnected || field.value !== editedValue) {
                state.dirtyFields.delete(field);
            }
        }
        return state.dirtyFields.size > 0;
    }

    function onActivity(event) {
        if (!event.isTrusted) return;
        state.lastActivity = Date.now();
        if (event.type === "click") {
            const submit = event.target.closest?.('[data-testid="stFormSubmitButton"]');
            if (submit) state.submittedForms.add(submit.closest('[data-testid="stForm"]'));
        }
        // Protect edits not yet sent to Python, including new-product text inputs.
        if (event.type === "input" || event.type === "change") {
            const field = event.target;
            if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
                const editable = field.type !== "password" && field.type !== "radio"
                    && field.type !== "checkbox" && field.type !== "button";
                const isDraft = field.closest('[data-testid="stForm"], .st-key-new_product_id, .st-key-new_product_name, .st-key-new_product_price');
                if (editable && isDraft && field.value !== "") {
                    state.dirtyFields.set(field, field.value);
                } else {
                    state.dirtyFields.delete(field);
                }
            }
        }
        updateStatus(false);
    }

    function updateStatus(idle) {
        const pending = data.hasPendingChanges || hasDirtyFields();
        status.textContent = pending
            ? "Automatisk frånkoppling pausad: spara eller rensa dina ändringar."
            : `Anslutningen avslutas efter ${timeoutMs / 60000} minuters inaktivitet.`;
        return idle && !pending;
    }

    function disconnect() {
        // A new local document unloads Streamlit and its WebSocket. Replacing HTML
        // in the existing document or st.stop() would leave the connection open.
        const idleDocument = document.implementation.createHTMLDocument("SmartLager – pausad");
        idleDocument.documentElement.lang = "sv";
        const charset = idleDocument.createElement("meta");
        charset.setAttribute("charset", "utf-8");
        idleDocument.head.prepend(charset);
        const viewport = idleDocument.createElement("meta");
        viewport.name = "viewport";
        viewport.content = "width=device-width, initial-scale=1";
        idleDocument.head.append(viewport);
        const title = idleDocument.createElement("h1");
        title.textContent = "SmartLager är pausad";
        const explanation = idleDocument.createElement("p");
        explanation.textContent = "Anslutningen avslutades på grund av inaktivitet. Klicka nedan för att fortsätta.";
        const reconnect = idleDocument.createElement("a");
        reconnect.textContent = "Anslut igen";
        reconnect.href = window.location.href;
        idleDocument.body.append(title, explanation, reconnect);
        const url = URL.createObjectURL(new Blob(
            ["<!doctype html>", idleDocument.documentElement.outerHTML],
            {type: "text/html;charset=utf-8"},
        ));
        window.location.replace(url);
    }

    function checkIdle() {
        if (stopped) return;
        const idle = Date.now() - state.lastActivity >= timeoutMs;
        if (updateStatus(idle)) disconnect();
    }

    const events = ["click", "pointerdown", "pointermove", "keydown", "input", "change", "wheel", "touchstart"];
    for (const event of events) {
        document.addEventListener(event, onActivity, {capture: true, passive: true});
    }
    // Background tabs throttle timers. Check elapsed wall time when the tab returns;
    // visibility alone must not reset inactivity and keep an abandoned session alive.
    document.addEventListener("visibilitychange", checkIdle);
    const timer = window.setInterval(checkIdle, 5000);
    updateStatus(false);

    const cleanup = () => {
        stopped = true;
        window.clearInterval(timer);
        for (const event of events) document.removeEventListener(event, onActivity, true);
        document.removeEventListener("visibilitychange", checkIdle);
    };
    state.cleanup = cleanup;
    return cleanup;
}
