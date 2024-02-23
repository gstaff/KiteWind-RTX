() => {
    function gradioApp() {
        const elems = document.getElementsByTagName('gradio-app');
        const elem = elems.length == 0 ? document : elems[0];

        if (elem !== document) {
            elem.getElementById = function(id) {
                return document.getElementById(id);
            };
        }
        return elem.shadowRoot ? elem.shadowRoot : elem;
    }
    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key == "`") { // CTRL + ` key
            const recordButtons = [...gradioApp().querySelectorAll('button.record.record-button')].filter(x => x.checkVisibility());
            const stopButtons = [...gradioApp().querySelectorAll('button.stop-button')].filter(x => x.checkVisibility());
            for (let button of recordButtons.concat(stopButtons)) {
                button.click();
            }
        }
    });
    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === " ") { // CTRL + Space key
            const updateButtons = gradioApp().querySelectorAll(".update-btn");
            for (let updateButton of updateButtons) {
                if (updateButton.checkVisibility()) {
                    updateButton.click();
                }
            }
        }
    });
}