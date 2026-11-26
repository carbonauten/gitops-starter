/** Decorative placeholder world-map graphic (not a georeferenced map). */
export function WorldMapGraphic() {
  return (
    <svg
      className="mk-world-map"
      viewBox="0 0 400 200"
      role="img"
      aria-label="Weltkarte mit Standorten"
      focusable="false"
    >
      <rect width="400" height="200" rx="12" fill="#eef3ec" />
      {[
        [60, 70],
        [90, 110],
        [160, 60],
        [190, 100],
        [230, 130],
        [270, 70],
        [310, 100],
        [340, 60],
        [120, 150],
        [250, 160],
      ].map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r={4} fill="#3f6e2c" opacity={0.75} />
      ))}
    </svg>
  );
}
