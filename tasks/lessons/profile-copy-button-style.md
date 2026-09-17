# Profile copy button style

The user requested info styling for all site copy buttons and the profile token
button inside its field. Use the shared `copy-button` component with sky-blue
background, darker hover, and white text. Keep this style during success/reset;
do not reintroduce per-feature green/slate classes. Reserve field padding for
the inset button and its longer Copied! label. Check feature CSS for unlayered
button selectors that could override the shared component.
