# Nodes 2.0 Studio integration

The viewer uses `nodeCreated`, `loadedGraphNode`, the public `executed` API event and `onNodeOutputsUpdated` for history restoration. It does not replace node prototypes. `recipe_json` uses the widget's `hidden` flag; FPS is a schema-declared advanced input. Inline editing uses `addDOMWidget`; the outer node retains ComfyUI's ports, header, resize handles, selection and subgraph behavior.

## One graph, one Studio

The Studio outputs its source VIDEO, recipe STRING and opaque `FOTUFILM_STUDIO` session. The session contains a unique execution token and the exact validated recipe. A downstream `FotufilmStudioReview` receives that session and a developed VIDEO, then returns UI metadata carrying the token. The frontend routes the result to the corresponding Studio. There is no backward wire and no graph cycle. Two Studios have independent sessions; execution paths inside subgraphs are resolved separately from history locator IDs.

Existing optional Studio preview inputs remain compatible, but must only receive independent upstream media. Do not connect the Studio's downstream render back to those inputs.

`FilmFinishSaveHDRMaster` now returns a `FOTUFILM_HDR_MASTER` handle to its existing EXR archive. `FotufilmDevelopHDRMaster` accepts that handle without copying or reuploading. The resolver requires the concrete handle type, a real ZIP file, and a path inside the server's output directory. The original uploaded-file path remains supported under the input directory. Grading still consumes the EXR master, never an 8-bit browser preview.

## Rendering and cache

The editor's Run workflow action saves the recipe and uses ComfyUI's normal queue. It may run LTX if no valid cached reconstruction exists. Recipe edits do not feed into the LTX subgraph; fixed-seed reconstruction can be reused in the same cache. No promise of cache survival across restarts or graph changes is made.

A completed preview records the rendered recipe. Later changes display a stale-preview message. Playback is browser-decoded video delivered by the ComfyUI server; a faster server accelerates rendering, not the browser decoder or network. This phase does not supply instantaneous grading or a calibrated HDR monitor. The preview demo uses a previously rendered native Fotufilm clip and labels its thumbnails as source thumbnails.

## Examples

- `Fotufilm - Studio.json`: source, Studio, Develop Video, Return to Studio.
- `Film Finish - Studio + LTX 2.5 HDR.json`: seven root nodes plus an instruction note. The LTX subgraph contains the original 25 model/conditioning/reconstruction/decode nodes. Open it for detailed inspection.
- `scripts/build_studio_workflows.py` regenerates both from the pinned grouped LTX lab. It preserves model names and transforms.

The expanded editor and dialog share the same implementation. Save persists the recipe; Cancel discards unsaved editor edits. Expanding/collapsing and opening the dialog do not start generation. Nodes 2.0 is enabled only in the isolated review deployment, never forced by the installed extension.
