let alfDialogResolve = null;

function showAlfDialog(message, options = {}) {
    const existing = document.querySelector("#alf-dialog");

    if (existing) {
        existing.remove();
    }

    const overlay = document.createElement("div");
    overlay.id = "alf-dialog";
    overlay.className = "alf-dialog-overlay";

    const dialog = document.createElement("div");
    dialog.className = "alf-dialog";

    const messageElement = document.createElement("div");
    messageElement.className = "alf-dialog-message";
    messageElement.textContent = message;

    dialog.append(messageElement);

    if (options.input) {
        const input = document.createElement("input");
        input.className = "alf-dialog-input";
        input.type = "text";
        input.value = options.value || "";
        input.setAttribute("aria-label", message);
        dialog.append(input);
    }

    const actions = document.createElement("div");
    actions.className = "alf-dialog-actions";

    if (options.cancel) {
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "alf-dialog-cancel";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", function () {
            closeAlfDialog(null);
        });
        actions.append(cancel);
    }

    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "alf-dialog-confirm";
    confirm.textContent = options.confirm || "OK";
    confirm.addEventListener("click", function () {
        const input = dialog.querySelector(".alf-dialog-input");

        closeAlfDialog(
            input ? input.value : true
        );
    });
    actions.append(confirm);

    dialog.append(actions);
    overlay.append(dialog);
    document.body.append(overlay);

    if (options.input) {
        const input = dialog.querySelector(".alf-dialog-input");
        input.focus();
        input.select();

        input.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                confirm.click();
            }

            if (event.key === "Escape") {
                closeAlfDialog(null);
            }
        });
    }

    return new Promise(function (resolve) {
        alfDialogResolve = resolve;
    });
}

function closeAlfDialog(value) {
    const overlay = document.querySelector("#alf-dialog");

    if (overlay) {
        overlay.remove();
    }

    if (alfDialogResolve) {
        const resolve = alfDialogResolve;
        alfDialogResolve = null;
        resolve(value);
    }
}

function alfAlert(message) {
    return showAlfDialog(message);
}

function alfConfirm(message) {
    return showAlfDialog(message, {
        cancel: true,
        confirm: "Confirm"
    });
}

function alfPrompt(message, value = "") {
    return showAlfDialog(message, {
        cancel: true,
        confirm: "OK",
        input: true,
        value: value
    });
}
