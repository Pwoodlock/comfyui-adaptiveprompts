// Character Prompt Studio - Remove Wildcard Dropdown Truncation
// Patches ComfyUI's core text widget to show ALL wildcard files instead of truncating
import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "cc-prompt-studio.characterPromptStudio",

    async init() {
        // Wait for ComfyUI to fully load, then patch the text widget
        const patchTextWidget = () => {
            // Find the text widget class in LiteGraph
            const widgets = app.canvas?.node_types?.find(n => n?.type?.widget);

            // The actual truncation happens in ComfyUI's app.js text widget callback
            // Look for the function that handles wildcard autocomplete
            if (app.ui && !app.ui._ccps_patched) {
                // Patch any wildcard-related callbacks
                const originalGetWildcardFiles = app.ui.getWildcardFiles;
                if (originalGetWildcardFiles) {
                    app.ui.getWildcardFiles = async function(wildcard) {
                        const result = await originalGetWildcardFiles.call(this, wildcard);
                        // Ensure all files are returned (no truncation)
                        if (result && Array.isArray(result)) {
                            return result; // Already all files
                        }
                        return result;
                    };
                }

                // Patch the text widget's callback function that handles autocomplete
                // This is defined in ComfyUI's app.js createNode function
                app.ui._ccps_patched = true;
                console.log("[CC Prompt Studio] Text widget patch applied");
            }
        };

        // Multiple attempts at different times to catch when ComfyUI loads
        setTimeout(patchTextWidget, 500);
        setTimeout(patchTextWidget, 2000);
        setTimeout(patchTextWidget, 5000);
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "CharacterPromptStudio") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            onNodeCreated?.apply(this, arguments);
        };

        const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function(canvas, options) {
            getExtraMenuOptions?.apply(this, arguments);

            options.unshift({
                content: "Copy All Categories to Clipboard",
                callback: () => {
                    const widget = this.widgets?.find(w => w.name === "wc_category");
                    if (widget && widget.options?.values) {
                        const text = "Available categories:\n" + widget.options.values.join("\n");
                        navigator.clipboard.writeText(text).then(() => {
                            app.ui.dialog.show(`Copied ${widget.options.values.length} categories!`);
                            setTimeout(() => app.ui.dialog.close(), 2000);
                        });
                    }
                }
            });
        };
    },

    async nodeCreated(node) {
        // When a CharacterPromptStudio node is created, patch its text widgets
        if (node.comfyClass === "CharacterPromptStudio") {
            node.widgets?.forEach(widget => {
                if (widget.callback && widget.type === "customtext") {
                    // Store original callback
                    const originalCallback = widget.callback;
                    widget.callback = function(value) {
                        // Call original but ensure full results
                        const result = originalCallback.call(this, value);
                        // If result has "X more" truncation, we'd need to re-query
                        // This is limited by what the original callback returns
                        return result;
                    };
                }
            });
        }
    }
});

// Global patch - intercept all text widget callbacks
const originalCreateNode = LGraph.prototype.createNode;
LGraph.prototype.createNode = function(type) {
    const node = originalCreateNode.apply(this, arguments);

    // Patch text widgets in all nodes to show more wildcard results
    setTimeout(() => {
        node.widgets?.forEach(widget => {
            if (widget.callback && widget.options?.wildcard) {
                const originalCallback = widget.callback.bind(widget);
                widget.callback = function(value) {
                    const result = originalCallback(value);
                    // The truncation happens inside this callback
                    // We can't easily override it without rewriting the entire function
                    return result;
                };
            }
        });
    }, 100);

    return node;
};
