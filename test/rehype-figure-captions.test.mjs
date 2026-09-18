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

test("assigns the stable varied sequence to sketches in document order", () => {
  const tree = {
    type: "root",
    children: [
      paragraphWithImage({ src: "/assets/sketch-fox.png", alt: "A fox sketch" }).children[0],
      paragraphWithImage({ src: "/assets/sketch-owl.png", alt: "An owl sketch" }).children[0],
      paragraphWithImage({ src: "/assets/sketch-trail.png", alt: "A trail sketch" }).children[0],
    ],
  };

  rehypeFigureCaptions()(tree);

  assert.equal(tree.children[0].properties.style, "--sketch-rotation: -8deg");
  assert.equal(tree.children[1].properties.style, "--sketch-rotation: 5deg");
  assert.equal(tree.children[2].properties.style, "--sketch-rotation: -3.5deg");
  assert.equal(sketchRotation(8), -8);
});

test("carries sketch tilt onto a generated figure", () => {
  const tree = paragraphWithImage({
    src: "/assets/sketch-owl.png",
    alt: "An owl sketch",
    title: "Owl study.",
  });

  rehypeFigureCaptions()(tree);

  assert.equal(tree.children[0].properties.style, "--sketch-rotation: -8deg");
});

test("tilts a sketch that shares its paragraph with text without converting it to a figure", () => {
  const tree = paragraphWithImage(
    { src: "/assets/sketch-map.png", alt: "A map sketch" },
    [{ type: "text", value: " A note beside the sketch." }],
  );

  rehypeFigureCaptions()(tree);

  assert.equal(tree.children[0].tagName, "p");
  assert.equal(tree.children[0].properties.style, "--sketch-rotation: -8deg");
});

test("does not assign tilt styling to ordinary photographs", () => {
  const tree = paragraphWithImage({ src: "/assets/sleet.png", alt: "Sleet" });

  rehypeFigureCaptions()(tree);

  assert.equal(tree.children[0].properties.style, undefined);
});
