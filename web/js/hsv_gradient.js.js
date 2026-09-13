import { app } from "../../../web/scripts/app.js";

app.registerExtension({
    name: "Antonioilev.PhotoshopHueSaturation",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "PhotoshopHueSaturation") {
            
            // Находим момент, когда нода создается на холсте
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // Находим виджет слайдера Hue
                const hueWidget = this.widgets.find(w => w.name === "hue");
                
                if (hueWidget) {
                    // Переопределяем отрисовку этого конкретного виджета
                    const originalDraw = hueWidget.draw;
                    hueWidget.draw = function(ctx, node, widget_width, y, widget_height) {
                        // Если это наш слайдер, рисуем под ним красивый радужный градиент
                        ctx.save();
                        let gradient = ctx.createLinearGradient(15, 0, widget_width - 30, 0);
                        gradient.addColorStop(0,   '#ff0000');
                        gradient.addColorStop(0.17, '#ffff00');
                        gradient.addColorStop(0.33, '#00ff00');
                        gradient.addColorStop(0.5,  '#00ffff');
                        gradient.addColorStop(0.66, '#0000ff');
                        gradient.addColorStop(0.83, '#ff00ff');
                        gradient.addColorStop(1,   '#ff0000');
                        
                        // Рисуем тонкую цветную полоску чуть ниже самого ползунка
                        ctx.fillStyle = gradient;
                        ctx.fillRect(15, y + widget_height - 6, widget_width - 30, 4);
                        ctx.restore();
                        
                        // Вызываем стандартную отрисовку поверх, чтобы ползунок не сломался
                        originalDraw.apply(this, arguments);
                    };
                }
                return r;
            };
        }
    }
});