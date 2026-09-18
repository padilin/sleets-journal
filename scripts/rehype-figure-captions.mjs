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

export function sketchRotation(source) {
  let hash = 2166136261;
  for (const character of source) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  const unsigned = hash >>> 0;
  const magnitude = 3 + ((unsigned >>> 1) / 0x7fffffff) * 5;
  return unsigned & 1 ? magnitude : -magnitude;
}

function sketchStyle(image, existingStyle = "") {
  const source = image?.properties?.src;
  if (typeof source !== "string" || !source.includes("/sketch-")) return existingStyle;
  const declaration = `--sketch-rotation: ${sketchRotation(source).toFixed(2)}deg`;
  return existingStyle ? `${existingStyle.replace(/;?\s*$/, "; ")}${declaration}` : declaration;
}

function transformChildren(parent) {
  if (!Array.isArray(parent.children)) return;

  for (let index = 0; index < parent.children.length; index += 1) {
    const child = parent.children[index];
    const image = imageOnlyChild(child);
    const caption = image?.properties?.title;

    if (image) {
      child.properties = {
        ...child.properties,
        style: sketchStyle(image, child.properties?.style),
      };
      if (!child.properties.style) delete child.properties.style;
    }

    if (image && typeof caption === "string" && caption.trim()) {
      const imageProperties = { ...image.properties };
      delete imageProperties.title;

      parent.children[index] = {
        type: "element",
        tagName: "figure",
        properties: {
          className: ["journal-figure"],
          ...(child.properties?.style ? { style: child.properties.style } : {}),
        },
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
