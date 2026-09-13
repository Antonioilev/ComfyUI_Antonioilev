/**
 * ComfyUI_Antonioilev Nodes Pack - 3D Mesh Preview & UI Colorizer
 * Multi-Node implementation for PBR and UV Preview
 * VERSION: Fully Independent Viewports (viewer.html vs viewer_3d_preview_save_load.html)
 * YEAR: 2026
 */

import { app } from "../../../scripts/app.js";

const EXTENSION_FOLDER = "ComfyUI_Antonioilev";

console.log("[ComfyUI_Antonioilev] Loading integrated mesh preview and colorizer extension in modular layout...");

app.registerExtension({
    name: "antonioilev.meshpreview_new",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        
        // --- ЧАСТЬ 1: ВИЗУАЛИЗАЦИЯ ЦВЕТОВ В НОДЕ COLORIZER ---
        if (nodeData.name === "AntonioilevMultiColorizer") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                const applyColorToWidget = (widget) => {
                    if (widget.name.startsWith("color_")) {
                        const color = widget.value;
                        if (widget.inputEl) {
                            widget.inputEl.style.backgroundColor = color;
                            const hex = color.replace('#', '');
                            const r = parseInt(hex.substr(0, 2), 16);
                            const g = parseInt(hex.substr(2, 2), 16);
                            const b = parseInt(hex.substr(4, 2), 16);
                            const brightness = (r * 299 + g * 587 + b * 114) / 1000;
                            widget.inputEl.style.color = brightness > 125 ? 'black' : 'white';
                            widget.inputEl.style.fontWeight = "bold";
                        }
                    }
                };

                this.onWidgetChange = function(name, value) {
                    if (name.startsWith("color_")) {
                        const w = this.widgets.find(w => w.name === name);
                        if (w) applyColorToWidget(w);
                    }
                };

                setTimeout(() => {
                    this.widgets.forEach(w => applyColorToWidget(w));
                }, 100);

                return r;
            };
        }

        // --- ЧАСТЬ 2: ДИНАМИЧЕСКИЕ ВЬЮПОРТЫ ДЛЯ 3D НОД ---
        const supportedPreviewNodes = [
            "3D View Save Load",
            "Ultimate3DViewSaveLoad"
        ];
        
        if (supportedPreviewNodes.includes(nodeData.name)) {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                const nodeRef = this;
                const MIN_VIEWPORT_WIDTH = 200;  
                const MIN_VIEWPORT_HEIGHT = 150;  

                // Создаем главный контейнер вьюпорта
                const container = document.createElement("div");
                container.style.width = "100%";
                container.style.height = "100%";
                container.style.position = "relative"; 
                container.style.boxSizing = "border-box";

                // Кнопка ручного обновления разметки (Update Layout)
                const htmlBtn = document.createElement("button");
                htmlBtn.innerHTML = "🔄 Update Layout";
                htmlBtn.style.position = "absolute";
                htmlBtn.style.top = "6px";
                htmlBtn.style.right = "6px";
                htmlBtn.style.zIndex = "10"; 
                htmlBtn.style.height = "24px"; 
                htmlBtn.style.padding = "2px 8px";
                htmlBtn.style.background = "rgba(42, 26, 79, 0.85)";
                htmlBtn.style.border = "1px solid #52339b";
                htmlBtn.style.borderRadius = "4px";
                htmlBtn.style.color = "#ffffff";
                htmlBtn.style.cursor = "pointer";
                htmlBtn.style.fontSize = "11px";
                htmlBtn.style.fontWeight = "bold";
                htmlBtn.style.fontFamily = "sans-serif";
                htmlBtn.style.transition = "background 0.2s, border-color 0.2s";
                htmlBtn.style.boxSizing = "border-box";
                htmlBtn.style.boxShadow = "0 2px 4px rgba(0,0,0,0.5)";

                htmlBtn.addEventListener("mouseenter", () => htmlBtn.style.background = "rgba(82, 51, 155, 0.95)");
                htmlBtn.addEventListener("mouseleave", () => {
                    htmlBtn.style.background = nodeRef.bgcolor ? nodeRef.bgcolor : "rgba(42, 26, 79, 0.85)";
                });
                
                // Сохраняем ссылку на ноду, чтобы гарантировать доступ к виджетам и вьюпорту
				const node = this;

				htmlBtn.addEventListener("click", (e) => {
					e.preventDefault();
					e.stopPropagation();
					
					// 1. Обновляем размеры самого окна вьюпорта
					forceUpdateViewportDimensions();
					
					// 2. Мгновенно обновляем размер кубиков в 3D сцене на лету
					if (node.widgets) {
						// Проверяем все возможные имена виджета размера, которые используются в твоем паке
						const sizeWidget = node.widgets.find(w => w.name === "point_size" || w.name === "voxel_scale" || w.name === "cube_size");
						
						if (sizeWidget && node.viewer) {
							const newScale = parseFloat(sizeWidget.value);
							
							// Если твой вьюпорт реализован через iframe, отправляем postMessage
							if (typeof node.viewer.postMessage === "function") {
								node.viewer.postMessage({
									type: "SET_VOXEL_SCALE",
									scale: newScale
								}, "*");
							} 
							// Если это кастомный класс с прямым методом изменения масштаба
							else if (typeof node.viewer.updateVoxelScale === "function") {
								node.viewer.updateVoxelScale(newScale);
							}
							// Если это встроенная сцена Three.js / Babylon
							else if (node.viewer.scene && typeof node.viewer.updatePointSize === "function") {
								node.viewer.updatePointSize(newScale);
							}
						}
					}
					
					// 3. Сохраняем состояние топологии на бэкенд
					sendTopologyState();
					
					// 4. Перерисовываем холст ComfyUI
					if (app.canvas) app.canvas.setDirty(true, true);
					
					// =====================================================
					// 5. ДОПОЛНЕНИЕ: ЗАПУСК КАК PLAY (ComfyUI QUEUE)
					// =====================================================

					// попытка стандартного запуска всего графа (Play кнопка)
					if (app.queuePrompt) {
						console.log("[ComfyUI_Antonioilev] Trigger: app.queuePrompt()");
						app.queuePrompt();
					} 
					// fallback для старых сборок ComfyUI
					else if (app.graph?.runQueue) {
						console.log("[ComfyUI_Antonioilev] Trigger: app.graph.runQueue()");
						app.graph.runQueue();
					} 
					// ещё один fallback (редкие форки)
					else if (app.graph?.queue) {
						console.log("[ComfyUI_Antonioilev] Trigger: app.graph.queue()");
						app.graph.queue();
					} 
					else {
						console.warn("[ComfyUI_Antonioilev] No ComfyUI execution method found");
					}
					
					
				});

                container.appendChild(htmlBtn);

                // Панель отображения метрик и переключения контекстов (Топология)
                const controlsPanel = document.createElement("div");
                controlsPanel.className = "antonioilev-topology-panel";
                controlsPanel.style.cssText = `
                    position: absolute !important;
                    top: 6px !important;
                    left: 6px !important;
                    z-index: 999999 !important;
                    display: flex !important;
                    flex-direction: column !important;
                    gap: 4px !important;
                    background: rgba(20, 20, 20, 0.85) !important;
                    padding: 6px 8px !important;
                    border-radius: 4px !important;
                    border: 1px solid rgba(255, 255, 255, 0.15) !important;
                    font-family: sans-serif !important;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.7) !important;
                    backdrop-filter: blur(4px) !important;
                    pointer-events: auto !important;
                `;

                const createCheckboxHelper = (id, text, checkedByDefault) => {
                    const label = document.createElement("label");
                    label.style.cssText = `
                        display: flex !important;
                        align-items: center !important;
                        gap: 6px !important;
                        color: #ffffff !important;
                        font-size: 11px !important;
                        font-weight: bold !important;
                        cursor: pointer !important;
                        user-select: none !important;
                    `;

                    const cb = document.createElement("input");
                    cb.type = "checkbox";
                    cb.checked = checkedByDefault;
                    cb.style.cssText = `
                        margin: 0 !important;
                        cursor: pointer !important;
                        accent-color: #52339b !important;
                    `;

                    label.appendChild(cb);
                    label.appendChild(document.createTextNode(text));
                    
                    const stopEvent = (e) => { e.stopPropagation(); };
                    label.addEventListener("click", stopEvent);
                    label.addEventListener("pointerdown", stopEvent);
                    cb.addEventListener("click", stopEvent);
                    cb.addEventListener("pointerdown", stopEvent);
                    
                    return { label, cb };
                };

                const texturedObj = createCheckboxHelper("cb_textured", "Textured", true);
                const wireframeObj = createCheckboxHelper("cb_wireframe", "Wireframe", false);

                const trisCounter = document.createElement("div");
                trisCounter.id = "antonioilev_dynamic_metrics";
                trisCounter.style.cssText = `
                    color: #00ffcc !important;
                    font-size: 11px !important;
                    font-weight: bold !important;
                    margin-bottom: 2px !important;
                    border-bottom: 1px solid rgba(255,255,255,0.15) !important;
                    padding-bottom: 4px !important;
                    font-family: monospace !important;
                `;
                trisCounter.innerText = "Tris: 0";

                controlsPanel.appendChild(trisCounter);
                controlsPanel.appendChild(texturedObj.label);
                controlsPanel.appendChild(wireframeObj.label);
                
                container.appendChild(controlsPanel);

                const sendTopologyState = () => {
                    if (iframe.contentWindow) {
                        iframe.contentWindow.postMessage({
                            type: "SET_TEXTURE_VISIBLE",
                            visible: texturedObj.cb.checked
                        }, "*");
                        iframe.contentWindow.postMessage({
                            type: "SET_WIREFRAME_VISIBLE",
                            visible: wireframeObj.cb.checked
                        }, "*");
                    }
                };

				texturedObj.cb.addEventListener("change", sendTopologyState);
				wireframeObj.cb.addEventListener("change", sendTopologyState);

				// --- ДОБАВЛЕНИЕ ПАНЕЛИ КООРДИНАТ (coordsLegend) ---
                const coordsLegend = document.createElement("div");
                coordsLegend.id = "ui_main_panel_outer";
                coordsLegend.style.cssText = `
                    position: absolute !important;
                    top: 6px !important;
                    left: 6px !important;
                    z-index: 999999 !important;
                    display: flex !important;
                    flex-direction: column !important;
                    gap: 2px !important;
                    background: rgba(20, 20, 20, 0.85) !important;
                    padding: 6px 8px !important;
                    border-radius: 4px !important;
                    border: 1px solid rgba(0, 255, 204, 0.25) !important;
                    font-family: monospace !important;
                    font-size: 11px !important;
                    color: #00ffcc !important;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.7) !important;
                    backdrop-filter: blur(4px) !important;
                    pointer-events: none !important;
                    box-sizing: border-box !important;
                `;
                
                // Начальное состояние (будет перезаписываться из iframe)
                coordsLegend.innerHTML = `
                    <div>X: <span id="val_x">0.00</span></div>
                    <div>Y: <span id="val_y">0.00</span></div>
                    <div>Z: <span id="val_z">0.00</span></div>
                `;
                container.appendChild(coordsLegend);
                container.coordsLegend = coordsLegend;

                // Переменная для динамического отступа ноды (меняется в зависимости от контекста)
                let currentContextPadding = 85; 

                // Создаем iframe вьюпорта
                const iframe = document.createElement("iframe");
                iframe.style.width = "100%";
                iframe.style.height = "100%";
                iframe.style.border = "none";
                iframe.style.backgroundColor = "#000000";
                iframe.style.display = "block";
                iframe.style.pointerEvents = "auto"; 
                iframe.style.boxSizing = "border-box";

                // ТОЧНОЕ РАЗДЕЛЕНИЕ ШАБЛОНОВ HTML
                const isUV = nodeData.name.toLowerCase().includes("uv");
                let targetHtml = "viewer_3d_preview_save_load.html";

                if (isUV) {
                    targetHtml = "viewer_uv.html";
                }

                const baseUrl = `/extensions/${EXTENSION_FOLDER}/${targetHtml}`;
                iframe.src = `${baseUrl}?v=${Date.now()}`;
                container.appendChild(iframe);

                // ДИНАМИЧЕСКИЙ СЛУШАТЕЛЬ КОНТЕКСТОВ ИЗ IFRAME
				window.addEventListener("message", (event) => {
					if (!event.data || event.data.type !== "UPDATE_UI_CONTEXT") return;
					
					const { context, htmlContent, linesCount } = event.data;
					
					// Обновляем DOM
					if (container.coordsLegend && htmlContent) {
						container.coordsLegend.innerHTML = htmlContent;
					}

					// ВАЖНО: Вместо глобальной переменной, сохраняем это в сам контейнер
					container.dataset.context = context;
					container.dataset.lines = linesCount || 0;
					
					// Даем микро-задержку браузеру на отрисовку обновленного DOM перед пересчетом
					requestAnimationFrame(() => {
						forceUpdateViewportDimensions();
					});
				});

                const forceUpdateViewportDimensions = () => {
					if (widget.hidden || !container || !nodeRef.size) return;

					const targetWidth = nodeRef.size[0];
					const targetHeight = nodeRef.size[1];
					const titleHeight = nodeRef.constructor.title_height || 30;

					// Считаем высоту виджетов динамически
					const nonPreviewWidgetsHeight = nodeRef.widgets
						.filter(w => w.type !== "MESH_PREVIEW")
						.reduce((acc, w) => acc + (w.computeSize?.(targetWidth)[1] || 24), 0);

					// ВЫЧИСЛЕНИЕ ПАДДИНГА:
					// Берем данные из дата-атрибутов, которые мы обновили выше
					const ctx = container.dataset.context;
					const lines = parseInt(container.dataset.lines) || 0;
					
					let nodePadding = 45; // Базовый
					if (container.coordsLegend?.style.display !== "none") {
						nodePadding = lines > 0 ? (35 + (lines * 16)) : 145;
					}

					const totalOccupiedHeight = titleHeight + nonPreviewWidgetsHeight + nodePadding;
					const iframeHeight = Math.max(MIN_VIEWPORT_HEIGHT, targetHeight - totalOccupiedHeight);

					container.style.height = `${iframeHeight}px`;
					
					// Если нужно обновить внутренности iframe
					if (iframe.contentWindow) {
						iframe.contentWindow.postMessage({ type: "FORCE_UPDATE_RESIZE" }, "*");
					}
				};

                const widget = this.addDOMWidget("preview", "MESH_PREVIEW", container, {
                    getValue() { return ""; },
                    setValue(v) { }
                });
                widget.size = [300, 430];

                widget.computeSize = function(width) {
                    const nodeWidth = width || 150;
                    if (this.hidden) return [nodeWidth, 0];
                    return [nodeWidth, MIN_VIEWPORT_HEIGHT]; 
                };

                let pendingSize = null;
                const applyFinal2DSize = () => {
                    if (!pendingSize) return;
                    forceUpdateViewportDimensions();
                    pendingSize = null;
                };

                window.addEventListener("mouseup", applyFinal2DSize);

                this.onResize = function(size) {
                    pendingSize = [size[0], size[1]];
                };

                // Изоляция событий прокрутки (WSL2 / Edge Canvas Hotfix)
                const blockSubEvents = (e) => {
                    if (e.type === "wheel") {
                        if (e.ctrlKey) {
                            e.preventDefault();
                            e.stopPropagation();
                            e.stopImmediatePropagation();
                        }
                    } else {
                        e.stopPropagation();
                    }
                };

                iframe.addEventListener("mouseenter", () => {
                    if (app.canvas && app.canvas.list_of_graphcanvas?.[0]) {
                        app.canvas.allow_searchbox = false;
                        app.canvas.list_of_graphcanvas[0].block_extra_canvas_drag_and_zoom = true;
                    }
                    window.addEventListener("wheel", blockSubEvents, { passive: false });
                    window.addEventListener("pointerdown", blockSubEvents, { passive: false });
                });

                iframe.addEventListener("mouseleave", () => {
                    if (app.canvas && app.canvas.list_of_graphcanvas?.[0]) {
                        app.canvas.allow_searchbox = true;
                        app.canvas.list_of_graphcanvas[0].block_extra_canvas_drag_and_zoom = false;
                    }
                    window.removeEventListener("wheel", blockSubEvents);
                    window.removeEventListener("pointerdown", blockSubEvents);
                });

                widget.element = container;
                
                const isAny3DViewNode = !isUV;

                if (isAny3DViewNode) {
                    widget.hidden = false;
                    container.style.display = "block";
                    setTimeout(() => { forceUpdateViewportDimensions(); }, 1);
                }

                this.setSize([300, 430]); 
                this.min_size = [10, 10];

                // Привязываем чекбоксы к контейнеру для хука onExecuted
                container.texturedLabel = texturedObj.label;
                container.wireframeLabel = wireframeObj.label;

                // Панель координатcoordsLegend теперь инициализируется как плавающий оверлей в контейнере (см. Часть 1)

                // --- ХУК ВЫПОЛНЕНИЯ И УПРАВЛЕНИЯ КОНТЕКСТАМИ ПАНЕЛЕЙ (С ОБРАБОТКОЙ ОШИБОК) ---
                const onExecuted = this.onExecuted;
                this.onExecuted = function(message) {
                    onExecuted?.apply(this, arguments);

                    const hasFile = message?.mesh_file && message.mesh_file.length > 0 && message.mesh_file[0] !== "";
                    const isError = message?.error || !hasFile;

                    if (isError) {
                        // Покраска ноды в стандартный цвет ошибки ComfyUI (Reddish/Crimson)
                        this.color = "#ff3333";
                        this.bgcolor = "#551111";
                        htmlBtn.style.background = "#551111";
                        htmlBtn.style.borderColor = "#ff3333";
                        console.warn(`[ComfyUI_Antonioilev] Mesh preview error: File not found or empty path in node "${nodeData.name}".`);
                    } else if (message?.color) {
                        this.color = message.color[0];   
                        this.bgcolor = message.color[1]; 
                        htmlBtn.style.background = message.color[1];
                        htmlBtn.style.borderColor = message.color[0];
                    } else {
                        // Сброс к дефолтным цветам ComfyUI, если файла нет, но ошибки не произошло
                        this.color = LGraphCanvas.node_colors.red ? LGraphCanvas.node_colors.red.color : "#333";
                        this.bgcolor = LGraphCanvas.node_colors.red ? LGraphCanvas.node_colors.red.bgcolor : "#222";
                    }
                    
                    if (!isUV) {
                        widget.hidden = false;
                        container.style.display = "block";
                    } else {
                        widget.hidden = !hasFile;
                        container.style.display = hasFile ? "block" : "none";
                    }

					const metricsPanel = container.querySelector("#antonioilev_dynamic_metrics");

                    // Определяем, пришли ли специфичные данные Trellis 2.0 (контекст или тип данных)
                    // Определяем режим с учетом контекста и переданного из Python поля "mode"
					const hasContext = message?.viewport_context && message.viewport_context.length > 0;
					const mode = message?.viewport_context?.[0]?.mode || "";

					// Учитываем тип сообщения, тип данных и явный "mode", пришедший из Python
					const isCoordsMode = (
						message?.type === "coords" || 
						message?.datatype === "coords" || 
						mode === "coords" || 
						(hasContext && message.viewport_context[0].context_type === "coords")
					);
                    // БЕЗОПАСНАЯ ДИСПЕТЧЕРИЗАЦИЯ КОНТЕКСТОВ (С ИНТЕГРАЦИЕЙ MESH И SHAPE SLAT)
                    const currentDataType = message?.type || message?.datatype || "";
                    const isMeshMode = currentDataType === "mesh";
                    const isSlatMode = currentDataType === "slat" || currentDataType === "shape_slat";

                    if (hasContext) {
						const ctx = message.viewport_context[0];
						
						// ЛОГИКА ОТРИСОВКИ ЛЕГЕНДЫ
						if (container.coordsLegend) {
							// Если это режим COORDS и есть данные — рисуем
							if (ctx.mode === "coords" && ctx.legend_items && Array.isArray(ctx.legend_items)) {
								container.coordsLegend.innerHTML = ""; 
								ctx.legend_items.forEach(item => {
									const row = document.createElement("div");
									row.style.display = "flex";
									row.style.alignItems = "center";
									row.style.margin = "2px 0";
									row.style.fontSize = "10px";
									
									const colorBox = document.createElement("div");
									colorBox.style.width = "10px";
									colorBox.style.height = "10px";
									colorBox.style.backgroundColor = item.color;
									colorBox.style.marginRight = "8px";
									colorBox.style.borderRadius = "2px";
									
									const label = document.createElement("span");
									label.innerText = item.label;
									label.style.color = "#ffffff";
									
									row.appendChild(colorBox);
									row.appendChild(label);
									container.coordsLegend.appendChild(row);
								});
								container.coordsLegend.style.display = "flex"; // Обязательно включаем отображение
								container.coordsLegend.style.marginBottom = "10px"; // Сдвигаем легенду вниз
							} 
							// Если режим SLAT или другой — очищаем и скрываем
							else if (ctx.mode === "slat" || ctx.mode !== "coords") {
								container.coordsLegend.innerHTML = "";
								container.coordsLegend.style.display = "none"; // Принудительно прячем
							}
						}
                        
                        // ЛОГИКА ТЕКСТА
                        if (!ctx.metrics_string || ctx.metrics_string.trim() === "") {
                            if (metricsPanel) metricsPanel.style.display = "none";
                        } else {
                            if (metricsPanel) {
                                metricsPanel.style.display = "block";
                                metricsPanel.innerText = ctx.metrics_string;
                            }
                        }
                                                
                        // ЛОГИКА УПРАВЛЕНИЯ ЭЛЕМЕНТАМИ
                        if (container.texturedLabel) container.texturedLabel.style.display = ctx.controls?.show_textured_checkbox ? "flex" : "none";
                        if (container.wireframeLabel) container.wireframeLabel.style.display = ctx.controls?.show_wireframe_checkbox ? "flex" : "none";
                        
                        // РАЗНЕСЕНИЕ COORDS И SLAT ДЛЯ ВИДИМОСТИ ЛЕГЕНДЫ
                        if (container.coordsLegend) {
                            if (ctx.mode === "coords") {
                                container.coordsLegend.style.display = "flex";
                            } else if (ctx.mode === "slat") {
                                container.coordsLegend.style.display = "none";
                            } else {
                                container.coordsLegend.style.display = isCoordsMode ? "flex" : "none";
                            }
                        }

                        // ЛОГИКА ПАНЕЛИ УПРАВЛЕНИЯ
                        const hasVisibleControls = ctx.controls?.show_textured_checkbox || ctx.controls?.show_wireframe_checkbox || isCoordsMode;
                        const hasVisibleText = ctx.metrics_string && ctx.metrics_string.trim() !== "";
                        if (controlsPanel) {
                            controlsPanel.style.display = (hasVisibleControls || hasVisibleText) ? "flex" : "none";
                        }
                                                
                        setTimeout(() => { forceUpdateViewportDimensions(); }, 1);

                    } else if (isCoordsMode || isSlatMode) {
                        // РЕЖИМ ТОЧЕК ИЛИ СЛАТОВ
                        if (metricsPanel) metricsPanel.style.display = "none";
                        if (container.texturedLabel) container.texturedLabel.style.display = "none";
                        if (container.wireframeLabel) container.wireframeLabel.style.display = "none";
                        
                        // РАЗНЕСЕНИЕ COORDS И SLAT В ФОЛБЕКЕ
                        if (container.coordsLegend) {
                            if (isCoordsMode) {
                                container.coordsLegend.style.display = "flex";
                            } else if (isSlatMode) {
                                container.coordsLegend.style.display = "none";
                            } else {
                                container.coordsLegend.style.display = "none";
                            }
                        }
                        
                        if (controlsPanel) controlsPanel.style.display = "flex";
                        
                        setTimeout(() => { forceUpdateViewportDimensions(); }, 1);

                    } else if (isMeshMode) {
    
						// ЯВНЫЙ РЕЖИМ ГОТОВОГО МЕША ОТ TRELLIS 2.0
						if (controlsPanel) controlsPanel.style.display = "flex";

						if (metricsPanel) {
							metricsPanel.style.display = "block";
							const count = message?.tri_count ? message.tri_count[0] : 0;
							metricsPanel.innerText = `Tris: ${Number(count).toLocaleString()}`;
						}

						if (container.texturedLabel) container.texturedLabel.style.display = "flex";
						if (container.wireframeLabel) container.wireframeLabel.style.display = "flex";

						// 🔥 ВОТ ЭТА СТРОКА — ВКЛЮЧЕНИЕ AXES UI
						if (container.axesLabel) container.axesLabel.style.display = "flex";

						if (container.voxelSlider) container.voxelSlider.style.display = "none";
					} else {
                        // КЛАССИЧЕСКИЙ ФОЛБЕК (Для остальных 3D нод без контекста)
                        if (controlsPanel) controlsPanel.style.display = "flex";
                        if (metricsPanel) {
                            metricsPanel.style.display = "block";
                            const count = message?.tri_count ? message.tri_count[0] : 0;
                            metricsPanel.innerText = `Tris: ${Number(count).toLocaleString()}`;
                        }
                        if (container.texturedLabel) container.texturedLabel.style.display = "flex";
                        if (container.wireframeLabel) container.wireframeLabel.style.display = "flex";
                        if (container.voxelSlider) container.voxelSlider.style.display = "none";
                    }

					// --- БЛОК ОБРАБОТКИ ОШИБОК И ОТПРАВКИ ФАЙЛА ВО ВЬЮПОРТ ---
                    // Сохраняем дефолтные цвета для сброса состояния ошибки
                    const defaultNodeColor = nodeRef.constructor.color || "#2a1a4f";
                    const defaultNodeBgColor = nodeRef.constructor.bgcolor || "#130f22";

                    // Функция перевода ноды в режим ошибки (красный цвет)
                    const setNodeErrorState = (isError) => {
                        if (isError) {
                            nodeRef.color = "#721c24";     // Бордовая рамка
                            nodeRef.bgcolor = "#45141c";   // Тёмно-красный фон ноды
                        } else {
                            // Возвращаем цвета, пришедшие с бэкенда, либо дефолтные
                            nodeRef.color = message?.color?.[0] || nodeRef.color || defaultNodeColor;
                            nodeRef.bgcolor = message?.color?.[1] || nodeRef.bgcolor || defaultNodeBgColor;
                        }
                        if (app.canvas) app.canvas.setDirty(true, true);
                    };

                    if (!hasFile) {
                        // Если файл вообще не пришёл или имя пустое — красим ноду в ошибку
                        setNodeErrorState(true);
                        if (metricsPanel) {
                            metricsPanel.style.display = "block";
                            metricsPanel.innerText = "ERROR: File Not Found";
                            metricsPanel.style.color = "#ff4a4a";
                        }
                    } else {
                        // Сбрасываем ошибку перед новой попыткой загрузки
                        setNodeErrorState(false);
                        if (metricsPanel) metricsPanel.style.color = "#00ffcc";

                        const filename = message.mesh_file[0];
                        const brightnessWidget = this.widgets.find(w => w.name === "brightness");
                        const currentBrightness = brightnessWidget ? brightnessWidget.value : 1.2;

                        const normalized = filename.replace(/\\/g, '/');
                        let filepath;
                        const pathMatch = normalized.match(/(?:^|\/)(output|input|temp)\/(.+)$/);
                        
                        if (pathMatch) {
                            const [, type, relPath] = pathMatch;
                            const parts = relPath.split('/');
                            const fname = parts.pop();
                            const subfolder = parts.join('/');
                            filepath = `/view?filename=${encodeURIComponent(fname)}&type=${type}&subfolder=${encodeURIComponent(subfolder)}&t=${Date.now()}`;
                        } else {
                            filepath = `/view?filename=${encodeURIComponent(normalized)}&type=output&subfolder=&t=${Date.now()}`;
                        }

                                                // --- ENV URL из ответа ноды (Python должен отдать env_file / env_url) ---
                        let envUrl = "";
						const envFromMsg = message?.env_url?.[0] || message?.env_url
                            || message?.env_file?.[0] || message?.env_file
                            || message?.env_hdr_file?.[0] || message?.env_hdr_file
                            || message?.hdr_url?.[0] || message?.hdr_url
                            || "";
                        if (envFromMsg) {
                            const envNorm = String(envFromMsg).replace(/\\/g, "/");
                            const envMatch = envNorm.match(/(?:^|\/)(output|input|temp)\/(.+)$/);
                            if (envMatch) {
                                const [, envType, envRel] = envMatch;
                                const envParts = envRel.split("/");
                                const envFname = envParts.pop();
                                const envSub = envParts.join("/");
                                envUrl = `/view?filename=${encodeURIComponent(envFname)}&type=${envType}&subfolder=${encodeURIComponent(envSub)}&t=${Date.now()}`;
                            } else if (envNorm.startsWith("/view?")) {
                                envUrl = envNorm;
                            } else {
                                // просто имя файла в output
                                envUrl = `/view?filename=${encodeURIComponent(envNorm)}&type=output&subfolder=&t=${Date.now()}`;
                            }
                        } else {
							envUrl = ""; // явно: нет env
						}
						

                        const payload = {
                            type: isUV ? "LOAD_MESH_UV" : "LOAD_MESH",
                            filepath: filepath,
                            meshPath: filepath,
                            node_name: nodeData.name,
                            timestamp: Date.now(),
                            clear_scene: true,
                            options: {
                                compute_normals: true,
                                fix_multi_material: true,
                                //double_side: true,
								double_side: false,
                                brightness: currentBrightness,
                                use_pbr: true,
                                force_standard_material: true,
                                enable_metalness: true,
                                enable_roughness: true,
                                enable_emissive: true,
                                enable_normal_map: true,
                                metalness: 1.0,
                                roughness: 1.0,
                                emissive_intensity: 1.0,
                                // IBL
                                env_url: envUrl || null,          // null / "" → HTML сделает fallback
                                //env_exposure: Math.min(Math.max(Number(currentBrightness) || 1.2, 0.5), 3.0),
								env_exposure: 1.0,
                                env_intensity: 0.85
                            }
                        };

                        // Слушаем сообщения об ошибках загрузки и изменениях координат из самого iframe вьюпорта
                        const handleIframeMessages = (e) => {
                            if (e.source !== iframe.contentWindow) return;
                            
							// Приём динамических координат при взаимодействии с латентным облаком Trellis 2.0
                            if (e.data?.type === "UPDATE_COORDS" || e.data?.type === "MOUSE_MOVE_3D") {
                                // Достукиваемся до DOM-дерева внутри iframe
                                const iframeDoc = iframe.contentWindow?.document;
                                if (iframeDoc) {
                                    // Ищем новые элементы седьмой строки прямо в разметке вьюпорта
                                    const xEl = iframeDoc.getElementById("val_x");
                                    const yEl = iframeDoc.getElementById("val_y");
                                    const zEl = iframeDoc.getElementById("val_z");
                                    
                                    // Записываем значения с точностью до 3 знаков, как положено для латентов
                                    if (xEl && e.data.x !== undefined) xEl.innerText = Number(e.data.x).toFixed(3);
                                    if (yEl && e.data.y !== undefined) yEl.innerText = Number(e.data.y).toFixed(3);
                                    if (zEl && e.data.z !== undefined) zEl.innerText = Number(e.data.z).toFixed(3);
                                }
                            }

                            // Проверяем типы ошибок загрузки файла меша/координат
                            if (e.data?.type === "LOAD_ERROR" || e.data?.type === "ERROR" || e.data?.status === "error") {
                                setNodeErrorState(true);
                                if (metricsPanel) {
                                    metricsPanel.style.display = "block";
                                    metricsPanel.innerText = `ERROR: Read Failed`;
                                    metricsPanel.style.color = "#ff4a4a";
                                }
                            }
                            if (e.data?.type === "LOAD_SUCCESS" || e.data?.type === "MESH_LOADED") {
                                setNodeErrorState(false);
                            }
                        };

                        // Удаляем старый слушатель, если он был, и вешаем новый
                        window.removeEventListener("message", nodeRef._iframeErrorListener);
                        nodeRef._iframeErrorListener = handleIframeMessages;
                        window.addEventListener("message", handleIframeMessages);

                        const sendData = () => {
							if (iframe.contentWindow) {
								iframe.contentWindow.postMessage({ type: "CLEAR_SCENE" }, "*");
								setTimeout(() => {
									iframe.contentWindow.postMessage(payload, "*");
									sendTopologyState();

									// Всегда сообщаем про env (пустой = default lights)
									setTimeout(() => {
										iframe.contentWindow.postMessage({
											type: "SET_ENVIRONMENT",
											filepath: envUrl || "",
											options: {
												exposure: payload.options.env_exposure,
												env_intensity: payload.options.env_intensity
											}
										}, "*");
									}, 80);
								}, 30);
							}
						};

                        iframe.onload = () => {
                            setTimeout(() => {
                                sendData();
                                sendTopologyState();
                            }, 100);
                        };
                        if (iframe.contentDocument?.readyState === 'complete') {
                            sendData();
                        }
                    }

                    // --- ДИНАМИЧЕСКОЕ ОКРАШИВАНИЕ ЛИНКОВ В РЕЖИМЕ LOAD ONLY ---
                    const modeWidget = this.widgets?.find(w => w.name === "mode" || w.name === "gate_mode" || w.name === "action");
                    if (modeWidget && this.inputs) {
                        const isLoadOnly = String(modeWidget.value).toLowerCase().includes("load");
                        
                        this.inputs.forEach((input) => {
                            if (input.link !== null) {
                                const linkObj = app.graph.links[input.link];
                                if (linkObj) {
                                    // #3a3a3a — тёмно-серый цвет потухшего линка
                                    linkObj.color = isLoadOnly ? "#3a3a3a" : null;
                                }
                            }
                        });
                        // Обновляем холст для мгновенного применения цвета
                        if (app.canvas) app.canvas.setDirty(true, true);
                    }
                };
                return r;
            };
        }
    }
});