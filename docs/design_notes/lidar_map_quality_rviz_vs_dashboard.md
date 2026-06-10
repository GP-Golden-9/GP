# LIDAR Mapping and Visualization Quality Report

## Executive Summary

This report analyzes why a 2D LIDAR map generated with an RPLIDAR A1M8 appears clear and acceptable in RViz, but looks degraded or "bad" when visualized on a laptop dashboard or web UI. The analysis focuses on differences between RViz visualization and downstream map export/consumption, including map resolution, image conversion, topic selection, and SLAM configuration. It provides practical diagnostic steps and configuration recommendations suitable for a ROS-based multi‑robot system using an A1M8 scanner.

## Hardware and Software Context

RPLIDAR A1M8 is a low‑cost 360‑degree 2D LIDAR with a typical range up to 12 m, scan rate around 5.5 Hz, and sample rate above 8 kHz.[cite:8] It is widely used with ROS for 2D SLAM and occupancy grid mapping in indoor environments.[cite:14][cite:17] In a typical configuration, the A1M8 publishes `/scan` data through the `rplidar_ros` driver into a SLAM node such as `gmapping` or `slam_toolbox`, which publishes a `nav_msgs/OccupancyGrid` on `/map` that RViz visualizes in real time.[cite:17][cite:19]

When the map is later exported (for example using `map_saver` from `map_server`) and visualized in a custom dashboard or web interface, users often observe a noticeable drop in perceived quality compared with the RViz view.[cite:12][cite:15] This mismatch is generally caused by differences in how the map is encoded, saved, rescaled, or re‑interpreted, rather than an intrinsic limitation of the LIDAR itself.

## RViz vs. Dashboard Map Rendering

### RViz Rendering Characteristics

RViz subscribes directly to `/map` (type `nav_msgs/OccupancyGrid`) and renders the grid cells according to their occupancy probabilities, using the resolution and origin information stored in the map message.[cite:15][cite:18] RViz can dynamically adjust zoom level and uses internal color mapping for free, occupied, and unknown cells, often making the map appear smooth and visually clean.

Because RViz visualizes the raw occupancy grid rather than a pre‑rendered bitmap image, it is not affected by intermediate conversion steps (such as exporting to PGM/PNG) that may introduce artifacts or quality loss.[cite:15]

### Dashboard / Web UI Rendering Characteristics

Many dashboards or web UIs load maps from:

- Saved image files (e.g., PGM/PNG produced by `map_saver`), or
- Separate map topics (e.g., global or local costmaps), or
- A combination of a static map plus dynamic overlays.

Common ROS workflows save maps with:

```bash
rosrun map_server map_saver -f mymap
```

This produces a `mymap.pgm` image and a `mymap.yaml` metadata file describing resolution, origin, and thresholds.[cite:15][cite:21] When the dashboard loads `mymap.pgm` and stretches or scales it to fit the screen, or misinterprets the thresholds, the rendered result can look blurry, pixelated, or excessively noisy even if the underlying map is fine.[cite:22]

## Root Causes of Quality Degradation Outside RViz

### 1. Map Resolution and Scaling

The map resolution (e.g., 0.05 m per cell) determines how detailed the occupancy grid is.[cite:22] If the resolution is small (high detail, such as 0.02 m), the grid becomes very large and any noise from the LIDAR or odometry is visible as jagged edges and fuzzy walls.[cite:22] Conversely, if a low‑resolution map is enlarged aggressively in the dashboard to fill a large window, each grid cell becomes a large pixel, producing a blocky or “Minecraft‑like” view.

A ROS note on map resolution shows that mapping modules struggle more as resolution decreases, making it harder to match scan data to the existing map and increasing visible artifacts.[cite:22] The same document suggests that resolutions around 0.05 m are a reasonable compromise for indoor mapping with consumer‑grade LIDAR.[cite:22]

### 2. Differences Between OccupancyGrid and Saved Image

The `map_saver` tool converts `nav_msgs/OccupancyGrid` into a grayscale image plus a YAML file. Occupied, free, and unknown cells are mapped to pixel intensity ranges according to configurable thresholds (`occupied_thresh` and `free_thresh`).[cite:15] Several ROS users have reported that maps that look good in RViz appear degraded, overly dark, or almost blank after being saved as PGM.[cite:12][cite:15]

Typical problems include:

- Incorrect thresholds causing too many cells to be classified as occupied or free, reducing contrast.
- External image editors changing bit depth or grayscale mapping, corrupting occupancy semantics.
- Compression or resaving with different settings, introducing banding or blurring.

Because the dashboard often relies on the image file rather than the original OccupancyGrid, any degradation introduced at the export step is visible only outside RViz.[cite:15]

### 3. Subscribing to the Wrong Map Topic (Costmap vs. Static Map)

Navigation stacks such as `move_base` or `nav2` maintain global and local costmaps in addition to the primary `/map` produced by SLAM.[cite:21] Costmaps are often noisier, contain inflation layers around obstacles, and may include transient readings. If the dashboard subscribes to a costmap topic instead of the static SLAM map, the visualization can appear cluttered and “ugly” compared with the clean map in RViz.

The Husarion community reported a case where a pre‑built map was saved and then loaded via `map_server`, but the system continued to run SLAM in parallel and update `/map`, confusing the GUI and producing unexpected visuals.[cite:21] Ensuring that the dashboard subscribes to the intended static map topic and that SLAM is not overwriting it is critical for consistent rendering.

### 4. Image Post‑Processing Outside ROS

Opening the saved PGM in tools like Photoshop or GIMP and resaving it can change its grayscale palette or bit depth, breaking the assumptions ROS map loaders rely on.[cite:15] When such modified images are used as backgrounds or fed back into map servers, the resulting visualization can look significantly worse than the original RViz rendering, even if the visual difference seems minor in a typical image viewer.

For dashboards that only use the image as a background (not for navigation), mild rescaling using high‑quality interpolation (e.g., Lanczos) can improve appearance, but it is important not to alter the semantic mapping of occupancy values if the image will be reused inside ROS.[cite:15]

### 5. SLAM Configuration and LIDAR Limitations

Although the primary problem in the described scenario is usually visualization, SLAM parameters and sensor characteristics still influence perceived quality:

- High map resolution combined with noisy scans produces jagged walls.
- Inadequate odometry or TF errors cause walls to appear doubled or skewed.
- Throttling scans too aggressively reduces spatial density and makes maps look sparse.[cite:16][cite:22]

RPLIDAR A1M8, while effective for hobby and research robots, has limitations in range and precision compared with higher‑end scanners.[cite:8][cite:14] These limitations are acceptable for many indoor environments but need to be considered when choosing map resolution and update rates.

## Recommended Diagnostic Workflow

### 1. Verify Map Topic in Dashboard

1. Inspect the dashboard configuration (ROS bridge, WebSocket, or node parameters) to confirm which topic is used for the map.
2. Ensure the dashboard subscribes to the same `/map` topic that RViz uses, not global or local costmaps (such as `/move_base/global_costmap/costmap`).[cite:21]
3. Temporarily disable SLAM nodes after saving a static map and confirm that the map displayed in the dashboard remains consistent.

### 2. Compare PGM Output with RViz

1. Run SLAM until the map in RViz is satisfactory.
2. Save the map:

   ```bash
   rosrun map_server map_saver -f mymap
   ```

3. Open `mymap.pgm` in a regular image viewer on the laptop.
4. Compare the image with the RViz map:
   - If the PGM looks similar to RViz, the dashboard rendering is likely responsible for any quality loss.
   - If the PGM already looks degraded, adjust SLAM and `map_saver` parameters (resolution, thresholds).[cite:15]

### 3. Validate YAML Metadata

Open `mymap.yaml` and check:

- `resolution`: Should be a reasonable value for the environment, often around 0.05 m for indoor maps.[cite:22]
- `origin`: Must align with the expected map coordinate frame.
- `occupied_thresh` and `free_thresh`: Adjust if the map appears too dark/light or low contrast.

If the dashboard loads maps via `map_server` using this YAML, any mismatch between YAML and how the dashboard interprets resolution and origin can distort the visualization.[cite:21]

### 4. Reload Map via Map Server and RViz

1. Start `map_server` with the saved map:

   ```bash
   rosrun map_server map_server mymap.yaml
   ```

2. Start RViz and subscribe to `/map` from `map_server`.
3. Confirm that the reloaded map still looks good in RViz. If it does, the problem lies entirely in the dashboard pipeline rather than map generation.[cite:15][cite:21]

### 5. Inspect SLAM and TF Configuration

If artifacts are visible even in RViz:

- Adjust SLAM parameters such as `delta` (resolution), scan matching iterations, and update intervals.[cite:22]
- Check the TF tree to ensure correct transforms between `map`, `odom`, `base_link`, and `laser` frames.[cite:12]
- Confirm scan rate and that `rplidar_ros` is publishing consistent data without frequent dropouts.[cite:17]

## Best‑Practice Recommendations

### Map Resolution and SLAM Tuning

- Use a map resolution between 0.03 m and 0.07 m for indoor mapping with A1M8; 0.05 m is a common default that balances detail and noise.[cite:22]
- Avoid excessively fine resolutions unless odometry and sensor quality are strong, as this can make noise highly visible.[cite:22]
- Ensure `throttle_scans` is not too large so that enough LIDAR data contributes to each map update.[cite:22]

### Direct OccupancyGrid Streaming to Dashboard

- For highest fidelity, design the dashboard to subscribe directly to `/map` (`nav_msgs/OccupancyGrid`) via `rosbridge` (or equivalent) and render the grid on the client using a JS library (e.g., ros2djs or a custom renderer).
- This approach mirrors RViz behavior and avoids quality loss from intermediate image export and rescaling.[cite:19]

### Careful Map Export and Image Handling

- When static images are needed (e.g., background layers), keep the original PGM for ROS consumption and generate a separate upscaled PNG for visualization purposes only.
- Use high‑quality interpolation (such as Lanczos) when resizing the image for dashboards.
- Do not modify grayscale mapping or bit depth of the PGM that will be reloaded by `map_server`.

### Topic Hygiene and Node Management

- Ensure SLAM nodes are stopped after producing a final static map, so they do not continue to modify `/map` while `map_server` is serving the saved map.[cite:21]
- Keep global and local costmaps separate in visualizations, clearly labeling them if they are displayed alongside the static map.

## Conclusion

The discrepancy between a clean map in RViz and a poor‑quality map in a laptop dashboard is typically caused by the export and visualization pipeline rather than the RPLIDAR A1M8 hardware. Key factors include map resolution, image conversion by `map_saver`, incorrect topic selection (costmaps instead of static maps), and post‑processing of the saved map image. By verifying that the dashboard uses the same `/map` topic as RViz, carefully tuning SLAM resolution and thresholds, and, where possible, streaming the OccupancyGrid directly instead of relying on static images, it is possible to achieve dashboard map quality that closely matches or equals what is seen in RViz.[cite:8][cite:15][cite:21]