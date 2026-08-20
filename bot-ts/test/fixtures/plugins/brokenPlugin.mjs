export default {
  version: "broken",
  validate: () => {
    throw new Error("intentionally broken");
  },
  api: { label: "broken" },
};
