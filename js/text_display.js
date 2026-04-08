// CC LLM Janitor - Header Result Display
import { app } from "../../scripts/app.js";

app.registerExtension({
	name: "cc-prompt-studio.llmJanitorDisplay",

	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name !== "CCLLMJanitor") return;

		const onNodeCreated = nodeType.prototype.onNodeCreated;
		nodeType.prototype.onNodeCreated = function() {
			onNodeCreated?.apply(this, arguments);
			this.llm_result = "Ready...";
		};

		const onExecuted = nodeType.prototype.onExecuted;
		nodeType.prototype.onExecuted = function(message) {
			onExecuted?.apply(this, arguments);

			// Extract summary from outputs (second output)
			if (message?.output?.[1]) {
				const summary = message.output[1];
				// Take first line or 60 chars
				this.llm_result = summary.split('\n')[0].substring(0, 60);
				app.canvas.setDirty(true);
			}
		};

		// Draw in the header area (before widgets are drawn)
		const onDrawForeground = nodeType.prototype.onDrawForeground;
		nodeType.prototype.onDrawForeground = function(ctx) {
			// Draw original first
			onDrawForeground?.apply(this, arguments);

			if (this.flags?.collapsed) return;

			ctx.save();

			// Draw result in header area (top right, before the category tag)
			const tagWidth = ctx.measureText("cc-prompt-studio").width + 20;

			// Background for result text
			ctx.fillStyle = this.llm_result !== "Ready..." ? "rgba(76, 175, 80, 0.3)" : "rgba(100, 100, 100, 0.2)";
			ctx.beginPath();
			ctx.roundRect(this.size[0] - tagWidth - 160, 2, 155, 22, 4);
			ctx.fill();

			// Result text
			ctx.fillStyle = this.llm_result !== "Ready..." ? "#90EE90" : "#AAA";
			ctx.font = "11px Arial";
			ctx.textAlign = "right";
			ctx.fillText(this.llm_result, this.size[0] - tagWidth - 10, 17);

			ctx.restore();
		};
	}
});
