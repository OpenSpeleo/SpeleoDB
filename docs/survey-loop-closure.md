# Format-specific survey loop closure

`Project.build_geojson(source_file)` selects the source application's numerical
preset. Upload generation, historical rebuilds, Django admin operations, and the
GeoJSON management command all call this model method. Selection belongs on
`Project`, rather than in a second web solver or a caller-specific wrapper.

| Source      | Library preset                                                                               | Numerical policy                                                                                      |
| ----------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Compass     | `compass_lib.preset.InverseLengthWeightedL1SpatialSolver`                                    | Inverse-length weighted absolute XYZ errors, solved by native HiGHS                                   |
| Stalagmight | `openspeleo_lib.loop_closure.presets.LengthAzimuthWeightedLeastSquaresHorizontalSolver`      | Horizontal length/azimuth/section-quality weighting from Stalagmight's Closures Computed View         |
| Ariane      | `openspeleo_lib.loop_closure.presets.InverseLengthWeightedConjugateGradientHorizontalSolver` | Reference inverse-length weighted horizontal conjugate gradients from the solver inside Ariane's Line |

These are immutable configurations supplied by the numerical libraries. Web does
not recreate their weights, stopping rules, station substitutions, projection,
or optimization. All loop-closure calculations stay in `cave_closure`. There is
no new model field, migration, HTTP parameter, scheduler, or browser control.
The former `SurveyLoopClosure` Gaussian wrapper and its optional model argument
are removed; callers simply request the project's GeoJSON.

```python
geojson = project.build_geojson(source_file)
```

## Measurements, controls, and format boundaries

Compass loads MAK/DAT through `CompassInterface.load_project()` and passes its
own project model to `project_to_geojson()`. The export keeps the existing leg,
anchor, passage, and color settings. Its L1 preset uses the original propagated
measurement deltas, first-observation undirected deduplication, fixed XYZ
anchors, and the length floor declared by the preset. Fewer than two anchors
retains initial positions, matching the original Compass algorithm. Web does not
invent a second anchor or replace this with a Gaussian solver.

Ariane and Stalagmight readers produce ordinary OpenSpeleo surveys. After
`from_file()`, conversion uses only those common models; no downstream native
reader calls are introduced. Ariane uses the reference CG preset, including its
historical stopping rules, rather than the separate modern least-squares
configuration with similar weights. Targeted Ariane closure records equate
`FromID` with `ClosureToID`; their record `ID` is not a station target.
Target-less common-model closure records retain their station-identity meaning.
The source-format adapter owns that interpretation.

Stalagmight uses the independent horizontal axis variances derived from length,
true bearing, and section quality. This preset can adjust a closed loop with one
geographic anchor. Pending weighted closures become station identities in the
common model before native preparation. Stalagmight's weighted/batch adjusted
view is non-destructive; web never writes the adjusted view back to the source.
Both horizontal presets retain recorded depths; Compass's spatial preset adjusts
elevations while keeping its anchors fixed.

Explicit geographic coordinates remain authoritative. The libraries retain
coordinate provenance checks and the existing discrepancy guard before solving.
Web does not guess corrections, manufacture geographic controls, or rewrite
measurements. The model checks for active stations and usable geographic anchors
before requesting native preparation, preserving the existing expected omission
behavior instead of turning missing-control validation into a failed job.

A source flagged as already adjusted remains subject to the library's safety
checks. Web does not silently retry measured export or force acceptance of
adjusted measurements. In particular, a persisted Stalagmight `is_aligned` flag
is not proof of destructive adjustment: current native weighted/batch closures
are derived views, while Move closures have different alignment semantics.
Inconsistent or historical metadata must be resolved at the source adapter
boundary, with evidence; web does not reinterpret it.

Selecting the matching solver does not extend that boundary's other format
support. The current common-model Stalagmight adapter does not apply saved
manual section/station offset collections. Exact reproduction of those display
edits remains an adapter limitation, separate from weighted loop closure. Web
must not calculate offsets independently or fall back to a measured export and
claim it preserves the application's authored display geometry.

## Publication and existing maps

Missing sources, empty surveys, and missing geographic anchors remain expected
skips. Parser, coordinate-safety, and numerical failures retain their exception
chain, are logged with a traceback, and fail the existing conversion task.
Timeouts continue to escape through the existing task-timeout handling. A failed
replacement leaves the previous stored artifact intact.

Public/private maps, OGC endpoints, and downloadable archives consume stored
`ProjectGeoJSON` artifacts. They do not run the solver themselves. Existing
artifacts are skipped unless an operator explicitly requests recomputation; no
rebuild, source update, or deployment is triggered by this code change. Use the
existing admin operation or `build_project_geojsons --force-recompute` workflow
to replace older artifacts when authorized. Replacement retains the existing
GeoJSON revision updates and cache invalidation behavior. See
[historical conversion](project-geojson-command.md) and
[artifact retention](project-geojson-artifacts.md).

The standalone dependency manifests and lockfile must resolve library releases
containing these presets before deployment. Editable monorepo overlays are not
proof that the standalone web image has the same APIs. Release those libraries
and refresh the standalone lockfile before frozen deployment verification; do
not introduce sibling paths into standalone dependency declarations. Deploy
matching web and worker application code together. Native Linux wheels must be
built against a libc baseline supported by the standalone Compose base. An
editable build with a local Rust toolchain is not proof that the published wheel
can be installed into the Rust-free standalone image. Keep that image's base and
the native wheel build baseline compatible. Railway service configuration is
unchanged.

## Verification and performance

`surveys/tests/test_loop_closed_geojson.py` uses small real TML, SQLite, and
MAK/DAT sources to verify format-specific selection, changed loop geometry,
source-byte preservation, one-anchor Stalagmight closure, and expected missing
anchor behavior. The Compass comparison excludes randomly assigned section
colors from both preset equality and measured-output inequality, so display
metadata cannot mask a missing geometry adjustment. The storage/worker
comparison in `gis/tests/test_geojson_generation.py` checks that background
generation stores the same Stalagmight preset output. Existing upload,
requested-revision, failed-replacement, and historical rebuild tests retain
their boundaries.

Run these tests inside the existing application container, followed by the
relevant upload and historical-conversion suites. Required dependencies and
services must be available; missing prerequisites are verification blockers.
Neither a source-only check nor an editable local import qualifies an untested
standalone release.

Web adds only source parsing, preset selection, and a metadata check before the
existing numerical call. It does not perform an additional measured export or
add per-feature solver calls. Numerical allocation and execution limits remain
owned by the libraries and the existing background-task limits.
