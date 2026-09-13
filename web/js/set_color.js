import { app } from "../../../scripts/app.js";

app.registerExtension({
    name: "Antonioilev.SetColor",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "AntonioilevSetColor") {
            
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                setTimeout(() => {
                    if (!this.widgets) return;

                    const r_widget = this.widgets.find(w => w.name === "r");
                    const g_widget = this.widgets.find(w => w.name === "g");
                    const b_widget = this.widgets.find(w => w.name === "b");
                    const hex_widget = this.widgets.find(w => w.name === "hex_val");
                    const picker_widget = this.widgets.find(w => w.name === "visual_picker");
                    const pick_btn = this.widgets.find(w => w.name === "pick_screen");

                    if (!r_widget || !g_widget || !b_widget || !hex_widget || !picker_widget || !pick_btn) {
                        return;
                    }

                    const updateFromRGB = () => {
                        const toHex = (n) => {
                            let v = parseInt(n);
                            if (isNaN(v)) v = 0;
                            return Math.max(0, Math.min(255, v)).toString(16).padStart(2, '0');
                        };
                        const newHex = `#${toHex(r_widget.value)}${toHex(g_widget.value)}${toHex(b_widget.value)}`;
                        picker_widget.value = newHex;
                        hex_widget.value = newHex;
                    };

                    const updateFromHex = () => {
                        let val = String(hex_widget.value).replace("#", "");
                        if (val.length === 6) {
                            r_widget.value = parseInt(val.substring(0, 2), 16);
                            g_widget.value = parseInt(val.substring(2, 4), 16);
                            b_widget.value = parseInt(val.substring(4, 6), 16);
                            picker_widget.value = "#" + val;
                        }
                    };

                    // ЛОГИКА ПИПЕТКИ
                    pick_btn.callback = async () => {
                        if (!window.EyeDropper) {
                            alert("EyeDropper API не поддерживается вашим браузером (нужен Chrome/Edge)");
                            return;
                        }
                        
                        const eyeDropper = new window.EyeDropper();
                        try {
                            const result = await eyeDropper.open();
                            hex_widget.value = result.sRGBHex;
                            updateFromHex();
                            // Сбрасываем кнопку обратно
                            pick_btn.value = false;
                        } catch (e) {
                            pick_btn.value = false;
                        }
                    };

                    r_widget.callback = updateFromRGB;
                    g_widget.callback = updateFromRGB;
                    b_widget.callback = updateFromRGB;
                    
                    hex_widget.callback = updateFromHex;
                    
                    picker_widget.callback = () => {
                        hex_widget.value = picker_widget.value;
                        updateFromHex();
                    };

                    updateFromHex();
                }, 1);

                return r;
            };
        }
    }
});