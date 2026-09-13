import { app } from "../../../scripts/app.js";

app.registerExtension({
    // 1. Имя расширения (можно оставить старое, но для порядка лучше тоже сменить)
    name: "Antonioilev.View2DSaveLoad", 
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        // 2. КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: проверяем соответствие новому имени класса из Python
        if (nodeData.name === "View2DSaveLoad") {
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                
                // Проверяем, пришел ли цвет из Python
                if (message?.color) {
                    this.color = message.color[0];
                    this.bgcolor = message.color[1];
                }
            };
        }
    },
});