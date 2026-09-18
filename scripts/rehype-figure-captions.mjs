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

function singleImageElement(node) {
  if (!isElement(node, "p") || !Array.isArray(node.children)) return undefined;
  const elementChildren = node.children.filter((child) => child.type === "element");
  if (elementChildren.length !== 1 || !isElement(elementChildren[0], "img")) return undefined;
  return elementChildren[0];
}

const SKETCH_ROTATIONS = [-8, 5, -3.5, 7, -5.5, 3, -7, 4.5];

export function sketchRotation(index) {
  return SKETCH_ROTATIONS[index % SKETCH_ROTATIONS.length];
}

function sketchStyle(image, index, existingStyle = "") {
  const source = image?.properties?.src;
  if (typeof source !== "string" || !source.includes("/sketch-")) return existingStyle;
  const declaration = `--sketch-rotation: ${sketchRotation(index)}deg`;
  return existingStyle ? `${existingStyle.replace(/;?\s*$/, "; ")}${declaration}` : declaration;
}

function transformChildren(parent, state) {
  if (!Array.isArray(parent.children)) return;

  for (let index = 0; index < parent.children.length; index += 1) {
    const child = parent.children[index];
    const image = imageOnlyChild(child);
    const sketchImage = singleImageElement(child);
    const caption = image?.properties?.title;

    if (sketchImage?.properties?.src?.includes("/sketch-")) {
      child.properties = {
        ...child.properties,
        style: sketchStyle(sketchImage, state.sketchIndex, child.properties?.style),
      };
      state.sketchIndex += 1;
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

    transformChildren(child, state);
  }
}

export function rehypeFigureCaptions() {
  return (tree) => transformChildren(tree, { sketchIndex: 0 });
}
