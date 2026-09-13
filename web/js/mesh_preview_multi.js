/**
 * ComfyUI GeomPack - Multi Mesh Preview Widget
 * Grid viewer for 1-4 meshes with synchronized cameras
 */

import { app } from "../../../scripts/app.js";

// Auto-detect extension folder name
const EXTENSION_FOLDER = (() => {
    const url = import.meta.url;
    const match = url.match(/\/extensions\/([^/]+)\//);
    return match ? match[1] : "ComfyUI-GeometryPack";
})();

console.log('[GeomPack Multi JS] Loading mesh_preview_multi.js extension');

app.registerExtension({
    name: "geompack.meshpreview.multi",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "GeomPackPreviewMeshMulti") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                // Viewer state persisted via DOM widget serialization
                const viewerState = { show_edges: false, camera_state: "", selected_field: "" };

                console.log('[GeomPack Multi JS] Creating PreviewMeshMulti node widget');

                // Create container for viewer + info panel
                const container = document.createElement("div");
                container.style.width = "100%";
                container.style.height = "100%";
                container.style.display = "flex";
                container.style.flexDirection = "column";
                container.style.backgroundColor = "#2a2a2a";

                // Create iframe for VTK.js viewer
                const iframe = document.createElement("iframe");
                iframe.style.width = "100%";
                iframe.style.flex = "1";
                iframe.style.minHeight = "450px";
                iframe.style.border = "none";
                iframe.style.backgroundColor = "#2a2a2a";
                iframe.src = `/extensions/${EXTENSION_FOLDER}/viewer_multi.html?v=` + Date.now();

                // Create mesh info panel
                const infoPanel = document.createElement("div");
                infoPanel.style.backgroundColor = "#1a1a1a";
                infoPanel.style.borderTop = "1px solid #444";
                infoPanel.style.padding = "6px 12px";
                infoPanel.style.fontSize = "10px";
                infoPanel.style.fontFamily = "monospace";
                infoPanel.style.color = "#ccc";
                infoPanel.style.lineHeight = "1.3";
                infoPanel.style.flexShrink = "0";
                infoPanel.style.overflow = "hidden";
                infoPanel.innerHTML = '<span style="color: #888;">Mesh info will appear here after execution</span>';

                container.appendChild(iframe);
                container.appendChild(infoPanel);

                // Add widget
                const widget = this.addDOMWidget("preview_multi", "MESH_PREVIEW_MULTI", container, {
                    getValue() { return JSON.stringify(viewerState); },
                    setValue(v) {
                        try { Object.assign(viewerState, JSON.parse(v)); } catch(e) {}
                    }
                });

                widget.computeSize = () => [768, 580];

                // Store references
                this.meshViewerIframeMulti = iframe;
                this.meshInfoPanelMulti = infoPanel;

                this.setSize(this.computeSize());

                // Bidirectional sync: viewer → node widgets (viewerState + real widgets)
                const node = this;
                window.addEventListener('message', (event) => {
                    if (event.data.type === 'WIDGET_UPDATE') {
                        const { widget: name, value } = event.data;
                        if (name in viewerState) viewerState[name] = value;
                        const w = node.widgets?.find(w => w.name === name);
                        if (w) w.value = value;
                    }
                });

                // Track iframe load state
                let iframeLoaded = false;
                iframe.addEventListener('load', () => {
                    iframeLoaded = true;
                    console.log('[GeomPack Multi] Iframe loaded');
                });

                // Set initial node size
                this.setSize([768, 580]);

                // Handle execution
                const onExecuted = this.onExecuted;
                this.onExecuted = function(message) {
                    onExecuted?.apply(this, arguments);

                    if (!message?.num_meshes) {
                        return;
                    }

                    const numMeshes = message.num_meshes[0];
                    const meshFiles = message.mesh_files[0];
                    const vertexCounts = message.vertex_counts[0];
                    const faceCounts = message.face_counts[0];
                    const gridCols = message.grid_cols[0];
                    const gridRows = message.grid_rows[0];

                    console.log(`[GeomPack Multi] onExecuted: ${numMeshes} meshes, grid ${gridCols}x${gridRows}`);

                    // Build info panel HTML
                    let infoHTML = `<div style="display: grid; grid-template-columns: auto repeat(${numMeshes}, 1fr); gap: 2px 12px;">`;
                    infoHTML += `<span style="color: #888;"></span>`;
                    for (let i = 0; i < numMeshes; i++) {
                        infoHTML += `<span style="color: #999; font-weight: bold; border-bottom: 1px solid #333;">Mesh ${i + 1}</span>`;
                    }
                    infoHTML += `<span style="color: #888;">Vertices:</span>`;
                    for (let i = 0; i < numMeshes; i++) {
                        infoHTML += `<span>${vertexCounts[i].toLocaleString()}</span>`;
                    }
                    infoHTML += `<span style="color: #888;">Faces:</span>`;
                    for (let i = 0; i < numMeshes; i++) {
                        infoHTML += `<span>${faceCounts[i].toLocaleString()}</span>`;
                    }
                    infoHTML += '</div>';
                    infoPanel.innerHTML = infoHTML;

                    // Prepare file paths
                    const filepaths = meshFiles.map(f => `/view?filename=${encodeURIComponent(f)}&type=output&subfolder=`);

                    const postMessageData = {
                        type: 'LOAD_MULTI_MESH',
                        numMeshes: numMeshes,
                        meshFiles: filepaths,
                        timestamp: Date.now(),
                        showEdges: viewerState.show_edges,
                        cameraState: viewerState.camera_state,
                        selectedField: viewerState.selected_field,
                    };

                    // Send message to iframe
                    const sendMessage = () => {
                        if (iframe.contentWindow) {
                            console.log('[GeomPack Multi] Sending message to iframe:', postMessageData);
                            iframe.contentWindow.postMessage(postMessageData, "*");
                        }
                    };

                    if (iframeLoaded) {
                        sendMessage();
                    } else {
                        iframe.addEventListener('load', sendMessage, { once: true });
                    }
                };

                return r;
            };
        }
    }
});
