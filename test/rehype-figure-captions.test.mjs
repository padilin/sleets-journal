import assert from "node:assert/strict";
import test from "node:test";
import { rehypeFigureCaptions } from "../scripts/rehype-figure-captions.mjs";

function paragraphWithImage(properties, additionalChildren = []) {
  return {
    type: "root",
    children: [
      {
        type: "element",
        tagName: "p",
        properties: {},
        children: [
          {
            type: "element",
            tagName: "img",
            properties,
            children: [],
          },
          ...additionalChildren,
        ],
      },
    ],
  };
}

test("turns a titled standalone image into a figure", () => {
  const tree = paragraphWithImage({ src: "/trail.png", alt: "A snowy trail", title: "Tracks at dusk." });

  rehypeFigureCaptions()(tree);

  const figure = tree.children[0];
  assert.equal(figure.tagName, "figure");
  assert.deepEqual(figure.properties.className, ["journal-figure"]);
  assert.equal(figure.children[0].tagName, "img");
  assert.equal(figure.children[0].properties.alt, "A snowy trail");
  assert.equal(figure.children[0].properties.title, undefined);
  assert.equal(figure.children[1].tagName, "figcaption");
  assert.equal(figure.children[1].children[0].value, "Tracks at dusk.");
});

test("leaves an image without a title unchanged", () => {
  const tree = paragraphWithImage({ src: "/trail.png", alt: "A snowy trail" });

  rehypeFigureCaptions()(tree);

  assert.equal(tree.children[0].tagName, "p");
});

test("leaves an image mixed with paragraph text unchanged", () => {
  const tree = paragraphWithImage(
    { src: "/trail.png", alt: "A snowy trail", title: "Tracks at dusk." },
    [{ type: "text", value: "More text" }],
  );

  rehypeFigureCaptions()(tree);

  assert.equal(tree.children[0].tagName, "p");
});
