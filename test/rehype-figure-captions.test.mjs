import assert from "node:assert/strict";
import test from "node:test";
import { rehypeFigureCaptions, sketchRotation } from "../scripts/rehype-figure-captions.mjs";

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

test("assigns a stable path-derived tilt to standalone sketch images", () => {
  const tree = paragraphWithImage({ src: "/assets/sketch-fox.png", alt: "A fox sketch" });

  rehypeFigureCaptions()(tree);

  const angle = sketchRotation("/assets/sketch-fox.png");
  assert.ok(Math.abs(angle) >= 3 && Math.abs(angle) <= 8);
  assert.equal(sketchRotation("/assets/sketch-fox.png"), angle);
  assert.equal(tree.children[0].properties.style, `--sketch-rotation: ${angle.toFixed(2)}deg`);
});

test("carries sketch tilt onto a generated figure", () => {
  const tree = paragraphWithImage({
    src: "/assets/sketch-owl.png",
    alt: "An owl sketch",
    title: "Owl study.",
  });

  rehypeFigureCaptions()(tree);

  assert.match(tree.children[0].properties.style, /^--sketch-rotation: -?\d+\.\d{2}deg$/);
});

test("does not assign tilt styling to ordinary photographs", () => {
  const tree = paragraphWithImage({ src: "/assets/sleet.png", alt: "Sleet" });

  rehypeFigureCaptions()(tree);

  assert.equal(tree.children[0].properties.style, undefined);
});
