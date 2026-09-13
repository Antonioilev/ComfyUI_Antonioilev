/**
 * ComfyUI Antonioilev - UV Mesh Preview Widget
 * Bridge Mode: Uses GeomPack viewer engine with Watertight Status
 */

import { app } from "../../../scripts/app.js";

const ORIGINAL_GEOM_PACK_FOLDER = "ComfyUI_Antonioilev";

let uvPreviewUIInstalled = false;

console.log("[Antonioilev] UV Preview Extension Loaded");

app.registerExtension({
    name: "antonioilev.meshpreviewuv",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "preview_mesh_uv" || uvPreviewUIInstalled) return;

        uvPreviewUIInstalled = true;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

            if (this._antonioilevUvPreviewCreated) return r;
            this._antonioilevUvPreviewCreated = true;

            console.log("[Antonioilev] Creating UI for:", this.type);

            const iframe = document.createElement("iframe");
            iframe.style.width = "100%";
            iframe.style.height = "100%";
            iframe.style.border = "none";
            iframe.style.backgroundColor = "#2a2a2a";
            iframe.style.aspectRatio = "2";

            iframe.src = `/extensions/${ORIGINAL_GEOM_PACK_FOLDER}/viewer_uv.html?v=`;

            const widget = this.addDOMWidget("uv_preview", "MESH_UV_PREVIEW", iframe, {
                getValue() { return ""; },
                setValue(v) {}
            });

            widget.computeSize = function(width) {
                const w = width || 600;
                const h = w / 2;
                return [w, h];
            };

            widget.element = iframe;
            this.uvViewerIframe = iframe;
            this.setSize([600, 350]);

            const onExecuted = this.onExecuted;
            this.onExecuted = function(message) {
                onExecuted?.apply(this, arguments);

                if (message?.mesh_file && message.mesh_file[0]) {
                    const isWatertight = message.is_watertight ? message.is_watertight[0] : false;
                    const statusIcon = isWatertight ? "✅" : "❌";

                    this.title = `🌀 UV Preview [WT: ${statusIcon}]`;
                    this.color = isWatertight ? "#224422" : "#442222";
                    this.bgcolor = isWatertight ? "#112211" : "#221111";

                    const meshFilename = message.mesh_file[0];
                    const uvDataFilename = message.uv_data_file ? message.uv_data_file[0] : null;

                    const meshPath = `/view?filename=${encodeURIComponent(meshFilename)}&type=output&subfolder=`;
                    const uvDataPath = uvDataFilename ?
                        `/view?filename=${encodeURIComponent(uvDataFilename)}&type=output&subfolder=` : null;

                    setTimeout(() => {
                        if (iframe.contentWindow) {
                            iframe.contentWindow.postMessage({
                                type: "LOAD_MESH_UV",
                                meshPath,
                                uvDataPath,
                                checker: message.show_checker ? message.show_checker[0] : false,
                                wireframe: message.show_wireframe ? message.show_wireframe[0] : true,
                                timestamp: Date.now()
                            }, "*");
                        }
                    }, 200);
                }
            };

            return r;
        };
    }
});