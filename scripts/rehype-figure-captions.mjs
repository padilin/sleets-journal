function isElement(node, tagName) {
  return node?.type === "element" && node.tagName === tagName;
}

function imageOnlyChild(node) {
  if (!isElement(node, "p") || !Array.isArray(node.children)) return undefined;

  const meaningfulChildren = node.children.filter(
    (child) => child.type !== "text" || child.value.trim() !== "",
  );

  if (meaningfulChildren.length !== 1 || !isElement(meaningfulChildren[0], "img")) return undefined;
  return meaningfulChildren[0];
}

function transformChildren(parent) {
  if (!Array.isArray(parent.children)) return;

  for (let index = 0; index < parent.children.length; index += 1) {
    const child = parent.children[index];
    const image = imageOnlyChild(child);
    const caption = image?.properties?.title;

    if (image && typeof caption === "string" && caption.trim()) {
      const imageProperties = { ...image.properties };
      delete imageProperties.title;

      parent.children[index] = {
        type: "element",
        tagName: "figure",
        properties: { className: ["journal-figure"] },
        children: [
          { ...image, properties: imageProperties },
          {
            type: "element",
            tagName: "figcaption",
            properties: {},
            children: [{ type: "text", value: caption.trim() }],
          },
        ],
        position: child.position,
      };
      continue;
    }

    transformChildren(child);
  }
}

export function rehypeFigureCaptions() {
  return (tree) => transformChildren(tree);
}
