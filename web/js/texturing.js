import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const EXTENSION_FOLDER = "ComfyUI_Antonioilev";
const HTML_FILE = "texturing.html";

// ============================================================================
// BACKEND → FRONTEND MATRIX CAPTURE TRIGGER
// ============================================================================
const messageHandlers = new Map();

api.addEventListener("antonioilev_capture_matrix", async (event) => {
    const targetNodeId = String(event.detail?.node_id);
    if (!targetNodeId) return;

    // ПРАВКА: Слушаем только если событие адресовано именно этой ноде (через контекст)
    // Но так как у нас расширение общее, добавим проверку:
    const targetNode = app.graph._nodes.find(n => String(n.id) === targetNodeId);
    
    // ВАЖНО: Если нода сейчас в режиме "Bake (from file)", мы вообще игнорируем запрос на захват
    const modeWidget = targetNode?.widgets?.find(w => w.name === "projection_mode");
    if (modeWidget && modeWidget.value === "Bake (from file)") {
        console.log(`[JS] Ignoring capture for node ${targetNodeId} (Mode: Bake from file)`);
        return;
    }
    if (!targetNode) {
        console.warn(`[JS] Node ${targetNodeId} not found`);
        return;
    }

    const widget = targetNode.widgets?.find(w => w.name === "preview");
    const iframe = widget?.element?.querySelector("iframe");

    if (!iframe || !iframe.contentWindow) {
        console.error(`[JS] iframe missing for node ${targetNodeId}`);
        return;
    }

    console.log(`[JS] Capturing camera matrix for node ${targetNodeId}`);

    // reset old listeners (CRITICAL FIX)
    window.onMessageCaptureMatrix = null;

    iframe.contentWindow.postMessage({ type: "GET_CAMERA_SNAPSHOT" }, "*");

	// ... внутри api.addEventListener("antonioilev_capture_matrix", ...)
    
    // ПРАВКА: Увеличиваем таймаут и добавляем отладку
    const camera_data = await new Promise((resolve) => {
        const handler = (e) => {
            // Проверка источника критична
            if (e.source !== iframe.contentWindow) return;

            if (e.data?.type === "CAMERA_SNAPSHOT") {
                console.log("[JS] Data caught from iframe:", e.data);
                window.removeEventListener("message", handler);
                resolve({
                    matrix: e.data.camera_matrix,
                    target: e.data.camera_target || [0, 0, 0] // Исправлено на [0,0,0] по умолчанию
					//zoom: e.data.zoom || 1.0,           
					//orthoSize: e.data.orthoSize || 5.0
                });
            }
        };
        
        window.addEventListener("message", handler);
        
        // Отправляем запрос
        iframe.contentWindow.postMessage({ type: "GET_CAMERA_SNAPSHOT" }, "*");

        // Увеличили время ожидания до 3 секунд
        setTimeout(() => {
            window.removeEventListener("message", handler);
            console.warn("[JS] Camera snapshot timed out");
            resolve(null);
        }, 15000);
    });

    if (!camera_data) {
        console.error("[JS] Failed to get camera data from iframe");
        return;
    }

    iframe.contentWindow.postMessage({
        type: "REQUEST_BAKE",
        camera_matrix: camera_data.matrix,
        camera_target: camera_data.target || [0, 0, 0], // Безопасное обращение
        node_id: targetNodeId,
        seed: performance.now()
    }, "*");

    // ============================================================
    // BAKE RESULT HANDLER
    // ============================================================
    const imageHandler = async (e) => {
        if (e.source !== iframe.contentWindow) return;

        if (e.data?.type === "BAKE_RESULT") {
            window.removeEventListener("message", imageHandler);

            const matrix = e.data.camera_matrix;
            const target = e.data.camera_target || [0, 0, 0];
			
			// ОБЪЯВЛЯЕМ ПЕРЕМЕННЫЕ ЗДЕСЬ
			const zoom = e.data.zoom || 1.0;
			const orthoSize = e.data.orthoSize || 5.0;

            console.log("[JS] Bake received:", {
                valid: Array.isArray(matrix) && matrix.length === 16,
            });

            if (!matrix || matrix.length !== 16) {
                console.error("[JS] Bad matrix returned from iframe");
                return;
            }

            try {
                // Используем данные, которые мы уже получили в camera_data 
                // и данные, которые пришли сейчас в e.data
                const body = {
                    image: e.data.image,
                    camera_matrix: matrix,
                    camera_target: target,
                    zoom: zoom,
                    ortho_size: orthoSize,
                    node_id: targetNodeId,
                    seed: e.data.seed || Date.now()
                };
                
                console.log("[DEBUG] Sending body:", body);
                
                const response = await fetch("/antonioilev/texturing/bake_texture", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body)
                });

                if (!response.ok) {
                    console.error("[JS] Backend error:", response.status);
                } else {
                    console.log("[JS] Sent to backend OK");
                }
            } catch (err) {
                console.error("[JS] Fetch failed:", err);
            }
        }
    };

    window.addEventListener("message", imageHandler);
});

// ============================================================================
// VIEWPORT SYNC HANDLER (Backend -> Frontend)
// ============================================================================
api.addEventListener("antonioilev_sync_viewport", (event) => {
    const data = event.detail;
	
	if (data.type === 'TOGGLE_GRID') {
        if (window.my3DViewer && window.my3DViewer.grid) {
            window.my3DViewer.grid.visible = data.visible;
            window.my3DViewer.render(); // Принудительная перерисовка
        }
    }
	
	if (data.type === "UPDATE_MESH") {
        const targetNode = app.graph._nodes.find(n => String(n.id) === String(data.node_id));
        const widget = targetNode?.widgets?.find(w => w.name === "preview");
        const iframe = widget?.element?.querySelector("iframe");

        if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage({
                type: "UPDATE_MESH",
                filename: data.mesh_filename
            }, "*");
        }
        return; // Завершаем обработку
    }
	
	if (data.type === "SET_NODE_COLOR") {
        const targetNode = app.graph._nodes.find(n => String(n.id) === String(data.node_id));
        if (targetNode) {
            if (data.mode === "Input_Screen") {
                targetNode.color = "#3355ff";   // Тёмный глубокий синий (ночной/индиго)
                targetNode.bgcolor = "#0A2E30"; // Фон
                
            } else if (data.mode === "Show Projection") {
                targetNode.color = "#2b2b2b";   // Графитовый серый
                targetNode.bgcolor = "#383838"; // Фон    
                
            } else if (data.mode === "Forward (Fast Draft)") {
                targetNode.color = "#2b2b2b";   // Графитовый серый
                targetNode.bgcolor = "#383838"; // Фон

			} else if (data.mode === "Bake (from file)") {
                targetNode.color = "#D4AF37";   // Тёмное золото (заголовок)
                targetNode.bgcolor = "#0A2E30"; // Глубокая бронза / тень (фон)
            } else {
                targetNode.color = "#2b2b2b";   // Дефолтный графитовый серый
                targetNode.bgcolor = "#383838";
            }
            
            app.graph.setDirtyCanvas(true);     // Принудительное обновление интерфейса
        }
        return;
    }
	
	
	
    const targetNodeId = String(data.node_id);
    
    const targetNode = app.graph._nodes.find(n => String(n.id) === targetNodeId);
    if (!targetNode) return;



	// --- ДОБАВЛЕННЫЙ БЛОК: Однократное обновление виджетов ---
    if (data.a_rad !== undefined || data.a_feather !== undefined) {
        ["a_rad", "a_feather"].forEach(name => {
            if (data[name] !== undefined) {
                const w = targetNode.widgets.find(w => w.name === name);
                // Проверяем, отличается ли текущее значение от нового, чтобы обновить только если нужно
                if (w && Math.abs(w.value - data[name]) > 0.0001) {
                    w.value = data[name];
                    if (w.callback) w.callback(w.value);
                }
            }
        });
    }
    // --------------------------------------------------------


    const widget = targetNode.widgets?.find(w => w.name === "preview");
    const iframe = widget?.element?.querySelector("iframe");

    if (iframe && iframe.contentWindow) {
        // ЕСЛИ ПРИШЛА КОМАНДА ОТРИСОВКИ МАСКИ
        if (data.type === "DRAW_MASK") {
            iframe.contentWindow.postMessage({
                type: "DRAW_MASK",
                a_rad: data.a_rad,
                a_feather: data.a_feather
            }, "*");
        } 
        // ИНАЧЕ (синхронизация камеры)
        else {
            iframe.contentWindow.postMessage({
                type: "SET_CAMERA_SNAPSHOT",
                camera_matrix: data.camera_matrix,
                camera_target: data.target,
                zoom: data.zoom,
                ortho_size: data.ortho_size,
                // ПРОКИДЫВАЕМ ПАРАМЕТРЫ СРАЗУ ПРИ СИНХРОНИЗАЦИИ КАМЕРЫ
                a_rad: data.a_rad,
                a_feather: data.a_feather
            }, "*");
        }
    }
});

// ============================================================================
// COMFYUI EXTENSION
// ============================================================================
app.registerExtension({
    name: "antonioilev.3d_texturing",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {

        const isTargetNode =
            nodeData.name === "ThreeDTexturing" ||
            nodeData.display_name === "3D texturing";

        if (!isTargetNode) return;

        console.log("[JS] Extension loaded:", nodeData.name);

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        const onExecuted = nodeType.prototype.onExecuted;

        // ============================================================
        // PY → UI UPDATE
        // ============================================================
        nodeType.prototype.onExecuted = function(message) {
            onExecuted?.apply(this, arguments);

            if (this.imgs) this.imgs = null;

            const widget = this.widgets?.find(w => w.name === "preview");
            const iframe = widget?.element?.querySelector("iframe");
            if (!iframe?.contentWindow) return;

            const send = (payload) => {
                if (iframe.dataset.loaded === "true") {
                    iframe.contentWindow.postMessage(payload, "*");
                } else {
                    iframe.onload = () => {
                        iframe.dataset.loaded = "true";
                        iframe.contentWindow.postMessage(payload, "*");
                    };
                }
            };

            if (message?.mesh_file?.length) {
                // Передаем имя файла и разрешаем iframe самому сформировать URL через /view
                // Это предотвратит путаницу с типами файлов внутри Three.js
                send({
                    type: "LOAD_MESH",
                    filename: message.mesh_file[0],
                    timestamp: Date.now()
                });
            }

            if (message?.overlay_file?.length) {
                const imgData = message.overlay_file[0];

                const url =
                    `/view?filename=${encodeURIComponent(imgData.filename)}`
                    + `&type=${imgData.type}`
                    + `&subfolder=${encodeURIComponent(imgData.subfolder || '')}`
                    + `&t=${Date.now()}`;

                send({
                    type: "UPDATE_OVERLAY",
                    url
                });
            }
            
            // Проброс параметров маски
            const a_rad = this.widgets.find(w => w.name === "a_rad")?.value;
            const a_feather = this.widgets.find(w => w.name === "a_feather")?.value;
            
            if (a_rad !== undefined && a_feather !== undefined) {
                send({
                    type: "DRAW_MASK",
                    a_rad: a_rad,
                    a_feather: a_feather
                });
            }
        };

        // ============================================================
        // HIDE DEFAULT PREVIEW
        // ============================================================
        nodeType.prototype.onDrawBackground = function(ctx) {
            if (this.imgs) this.imgs = null;
            if (this.image) this.image = null;

            if (this.generated_images_container) {
                this.generated_images_container.style.display = "none";
            }
        };

        const onDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function(ctx) {
            if (this.imgs) this.imgs = null;
            onDrawForeground?.apply(this, arguments);
        };

        // ============================================================
        // NODE UI INIT
        // ============================================================
        nodeType.prototype.onNodeCreated = function() {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

            const container = document.createElement("div");
            container.style.cssText =
                "width:100%;height:100%;position:relative;background:#000;overflow:hidden;";

            const iframe = document.createElement("iframe");
            iframe.src = `/extensions/${EXTENSION_FOLDER}/${HTML_FILE}?v=${Date.now()}`;
            iframe.style.cssText = "width:100%;height:100%;border:none;";
            iframe.dataset.loaded = "false";

            iframe.onload = () => iframe.dataset.loaded = "true";

            container.appendChild(iframe);

            setTimeout(() => {
                if (this.generated_images_container) {
                    this.generated_images_container.style.display = "none";
                }
            }, 10);

            this.addDOMWidget("preview", "MESH_PREVIEW", container);
            this.setSize([2048, 2048]);

            return r;
        };
    }
});