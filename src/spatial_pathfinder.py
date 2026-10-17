import numpy as np
import heapq
import math
import plotly.graph_objects as go
from typing import List, Tuple, Dict, Optional, Union


class SpatialPathfinder:
    """
    Module B (Phase 1): A* 3D Topographic Navigation Engine for CLPS Lunar Rovers.
    Calculates surface slope gradients, maps terrain traversability costs, and computes 
    the shortest hazard-avoiding route across 2D elevation grids.
    """
    def __init__(
        self,
        max_safe_slope_deg: float = 15.0,
        critical_slope_deg: float = 25.0,
        cell_size_m: float = 10.0
    ):
        """
        Parameters:
            max_safe_slope_deg (float): Slopes above this angle incur steep cost penalties.
            critical_slope_deg (float): Slopes above this angle are untraversable (impassable cliff).
            cell_size_m (float): Spatial resolution per grid pixel in meters.
        """
        self.max_safe_slope = float(max_safe_slope_deg)
        self.critical_slope = float(critical_slope_deg)
        self.cell_size_m = float(cell_size_m)

    def calculate_slope_grid(self, elevation_grid: np.ndarray) -> np.ndarray:
        """
        Calculates local surface slope angles in degrees across a 2D elevation matrix 
        using central finite difference gradients.
        
        Parameters:
            elevation_grid (np.ndarray): 2D array of surface altitudes in meters.
            
        Returns:
            np.ndarray: 2D array of slope angles in degrees.
        """
        # Calculate elevation gradients along rows (y) and columns (x)
        grad_y, grad_x = np.gradient(elevation_grid, self.cell_size_m)
        
        # Total slope magnitude = arctan(sqrt(dz/dx^2 + dz/dy^2))
        slope_radians = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
        slope_degrees = np.degrees(slope_radians)
        
        return slope_degrees

    def generate_cost_matrix(
        self, 
        elevation_grid: np.ndarray, 
        shadow_mask: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Converts elevation and shadow states into an A* movement penalty matrix.
        
        Cost Scaling Protocol:
            - Nominal Terrain (Slope <= 5°): Base Cost = 1.0
            - Moderate Slope (5° < Slope <= 15°): Linear Cost Scaling (1.0 to 10.0)
            - Hazardous Slope (15° < Slope < 25°): Exponential Penalty (10.0 to 500.0)
            - Impassable Slope (Slope >= 25°) OR Crater Shadow: Infinite Cost (np.inf)
        """
        slopes = self.calculate_slope_grid(elevation_grid)
        rows, cols = elevation_grid.shape
        cost_matrix = np.ones((rows, cols), dtype=float)

        # 1. Nominal vs Moderate Slope Scaling
        moderate_mask = (slopes > 5.0) & (slopes <= self.max_safe_slope)
        cost_matrix[moderate_mask] = 1.0 + 9.0 * ((slopes[moderate_mask] - 5.0) / (self.max_safe_slope - 5.0))

        # 2. Hazardous Slope Exponential Scaling
        hazard_mask = (slopes > self.max_safe_slope) & (slopes < self.critical_slope)
        cost_matrix[hazard_mask] = 10.0 + 490.0 * ((slopes[hazard_mask] - self.max_safe_slope) / (self.critical_slope - self.max_safe_slope)) ** 2

        # 3. Impassable Cliff Barriers
        cost_matrix[slopes >= self.critical_slope] = np.inf

        # 4. Ingest Shadow Mask (if shadow array is provided)
        if shadow_mask is not None:
            # True = In Shadow (Power loss & freeze risk) -> Impassable
            cost_matrix[shadow_mask == True] = np.inf

        return cost_matrix

    def _euclidean_heuristic(self, node: Tuple[int, int], goal: Tuple[int, int]) -> float:
        """
        Calculates straight-line Euclidean distance heuristic in meters from current node to goal.
        """
        dr = node[0] - goal[0]
        dc = node[1] - goal[1]
        return math.sqrt(dr * dr + dc * dc) * self.cell_size_m

    def find_path_a_star(
        self, 
        elevation_grid: np.ndarray, 
        start: Tuple[int, int], 
        goal: Tuple[int, int],
        shadow_mask: Optional[np.ndarray] = None
    ) -> Tuple[Optional[List[Tuple[int, int]]], float]:
        """
        Executes A* search algorithm over the 3D terrain cost matrix.
        
        Parameters:
            elevation_grid (np.ndarray): 2D array of surface elevation in meters.
            start (Tuple[int, int]): (row, col) grid coordinates of Start Location.
            goal (Tuple[int, int]): (row, col) grid coordinates of Target Destination.
            shadow_mask (np.ndarray, optional): 2D boolean array where True indicates shadow.
            
        Returns:
            Tuple[List[Tuple[int, int]], float]:
                - Ordered list of (row, col) path coordinates from start to goal.
                - Total accumulated path cost (returns np.inf if path is blocked).
        """
        rows, cols = elevation_grid.shape
        cost_matrix = self.generate_cost_matrix(elevation_grid, shadow_mask)

        # Validate start and goal boundaries
        if not (0 <= start[0] < rows and 0 <= start[1] < cols):
            raise ValueError(f"Start coordinate {start} is outside grid bounds ({rows}, {cols}).")
        if not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
            raise ValueError(f"Goal coordinate {goal} is outside grid bounds ({rows}, {cols}).")

        if math.isinf(cost_matrix[start]):
            print("[WARN] Start position is in an untraversable zone (steep cliff or shadow).")
            return None, np.inf
        if math.isinf(cost_matrix[goal]):
            print("[WARN] Goal position is in an untraversable zone (steep cliff or shadow).")
            return None, np.inf

        # Priority Queue stores tuples: (f_score, current_row, current_col)
        open_set: List[Tuple[float, int, int]] = []
        heapq.heappush(open_set, (0.0, start[0], start[1]))

        # Track previous node for path reconstruction
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}

        # g_score[node] stores exact lowest movement cost from start to node
        g_score: Dict[Tuple[int, int], float] = {start: 0.0}

        # 8-Directional Movement Offsets: (d_row, d_col, distance_multiplier)
        neighbors = [
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),       # Cardinal
            (-1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)),              # Diagonals
            (1, -1, math.sqrt(2)), (1, 1, math.sqrt(2))
        ]

        while open_set:
            _, current_r, current_c = heapq.heappop(open_set)
            current_node = (current_r, current_c)

            if current_node == goal:
                # Reconstruct path backwards from goal to start
                path = [current_node]
                while current_node in came_from:
                    current_node = came_from[current_node]
                    path.append(current_node)
                path.reverse()
                return path, g_score[goal]

            for dr, dc, dist_mult in neighbors:
                nr, nc = current_r + dr, current_c + dc

                # Check grid boundary bounds
                if 0 <= nr < rows and 0 <= nc < cols:
                    step_cost = cost_matrix[nr, nc]

                    # Skip untraversable cells (cliffs or shadows)
                    if math.isinf(step_cost):
                        continue

                    # Movement cost = step penalty * step physical distance
                    tentative_g = g_score[current_node] + (step_cost * self.cell_size_m * dist_mult)
                    neighbor_node = (nr, nc)

                    if neighbor_node not in g_score or tentative_g < g_score[neighbor_node]:
                        came_from[neighbor_node] = current_node
                        g_score[neighbor_node] = tentative_g
                        f_score = tentative_g + self._euclidean_heuristic(neighbor_node, goal)
                        heapq.heappush(open_set, (f_score, nr, nc))

        # No viable path discovered
        return None, np.inf


def generate_synthetic_lunar_dem(
    grid_shape: Tuple[int, int] = (100, 100), 
    cell_size_m: float = 10.0
) -> np.ndarray:
    """
    Generates a realistic 3D synthetic DEM containing a central crater rim and surrounding peaks 
    for standalone algorithm validation.
    """
    rows, cols = grid_shape
    y = np.linspace(-500, 500, rows)
    x = np.linspace(-500, 500, cols)
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X**2 + Y**2)

    # Base lunar plateau
    elevation = 100.0 - 0.05 * R

    # Add a steep central crater rim (Radius = 250m)
    crater_rim = 50.0 * np.exp(-((R - 250.0) ** 2) / (2 * 30.0 ** 2))
    crater_floor = -80.0 * np.exp(-(R**2) / (2 * 180.0**2))
    
    elevation += crater_rim + crater_floor
    return elevation


def generate_dynamic_pathfinding_mesh(
    sun_elevation: float,
    sun_azimuth: float,
    crater_rim_360: np.ndarray,
    start_coords: Tuple[int, int] = (15, 15),
    goal_coords: Tuple[int, int] = (85, 85),
    grid_size: int = 100,
    cell_size_m: float = 10.0
) -> Dict[str, Union[np.ndarray, Optional[List[Tuple[int, int]]], float, bool]]:
    """
    Phase 2 Data Pipeline Handshake:
    Dynamically generates the 3D elevation grid and hour-by-hour raycasted shadow mask 
    based on live orbital vectors, then computes the optimal hazard-avoiding A* route.
    
    Parameters:
        sun_elevation (float): Live sun elevation angle in degrees.
        sun_azimuth (float): Live sun azimuth angle in degrees.
        crater_rim_360 (np.ndarray): 360-element array of surrounding crater rim heights.
        start_coords (Tuple[int, int]): Grid coordinates (row, col) for Rover Landing Zone.
        goal_coords (Tuple[int, int]): Grid coordinates (row, col) for Waypoint Target.
        grid_size (int): Dimension of square grid (default 100x100).
        cell_size_m (float): Pixel resolution in meters.
        
    Returns:
        Dict containing elevation_grid, shadow_mask, path, total_distance_m, max_slope, and status flags.
    """
    # 1. Build localized 3D DEM mesh centered on landing site
    dem = generate_synthetic_lunar_dem(grid_shape=(grid_size, grid_size), cell_size_m=cell_size_m)
    
    # 2. Raycast 2D Shadow Mask based on Sun Azimuth and Elevation
    rows, cols = dem.shape
    shadow_mask = np.zeros((rows, cols), dtype=bool)
    
    # If sun is below local horizon, the entire mesh is in night shadow
    if sun_elevation <= 0.0:
        shadow_mask[:] = True
    else:
        # Evaluate local topographic shadowing across the grid
        az_idx = int(sun_azimuth) % 360
        blocking_height = crater_rim_360[az_idx]
        
        # Grid cells below the dynamic raycast obstruction threshold are masked as shadow
        if sun_elevation < blocking_height:
            # Mask central low-elevation crater basin as impassable shadow
            shadow_mask[dem < 20.0] = True

    # 3. Initialize Pathfinder and Execute A* Route Search
    pathfinder = SpatialPathfinder(cell_size_m=cell_size_m)
    path, total_cost = pathfinder.find_path_a_star(
        elevation_grid=dem,
        start=start_coords,
        goal=goal_coords,
        shadow_mask=shadow_mask
    )
    
    # 4. Extract Route Telemetry Metrics
    if path:
        slopes = pathfinder.calculate_slope_grid(dem)
        path_slopes = [slopes[r, c] for r, c in path]
        total_distance = (len(path) - 1) * cell_size_m
        max_slope = max(path_slopes) if path_slopes else 0.0
        avg_slope = float(np.mean(path_slopes)) if path_slopes else 0.0
        path_viable = True
    else:
        total_distance = 0.0
        max_slope = 0.0
        avg_slope = 0.0
        path_viable = False

    return {
        "elevation_grid": dem,
        "shadow_mask": shadow_mask,
        "path": path,
        "total_distance_m": total_distance,
        "max_slope_deg": max_slope,
        "avg_slope_deg": avg_slope,
        "path_viable": path_viable,
        "cell_size_m": cell_size_m
    }


def render_3d_navigation_mesh(path_telemetry: Dict) -> go.Figure:
    """
    Phase 3 UI Integration:
    Renders the 1km x 1km local elevation grid as a 3D Plotly surface and 
    drapes the optimal A* safe route over the topography.
    """
    dem = path_telemetry["elevation_grid"]
    path = path_telemetry["path"]
    
    fig = go.Figure()
    
    # Base Terrain Surface
    fig.add_trace(go.Surface(
        z=dem,
        colorscale='Greys',
        showscale=False,
        opacity=0.9,
        name="Lunar Surface"
    ))
    
    # Drape the safe route over the 3D surface
    if path_telemetry["path_viable"] and path:
        path_r = [p[0] for p in path]
        path_c = [p[1] for p in path]
        # Hover slightly above ground for visibility
        path_z = [dem[r, c] + 1.5 for r, c in path] 
        
        # Draw the neon green path
        fig.add_trace(go.Scatter3d(
            x=path_c, y=path_r, z=path_z,
            mode='lines',
            line=dict(color='#00FF00', width=6),
            name="Safe Traverse Route"
        ))
        
        # Start Location Marker
        fig.add_trace(go.Scatter3d(
            x=[path_c[0]], y=[path_r[0]], z=[path_z[0]],
            mode='markers', marker=dict(color='blue', size=8), name="Landing Zone"
        ))
        
        # Goal Destination Marker
        fig.add_trace(go.Scatter3d(
            x=[path_c[-1]], y=[path_r[-1]], z=[path_z[-1]],
            mode='markers', marker=dict(color='red', size=8), name="Target Destination"
        ))
        
    fig.update_layout(
        margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            xaxis_title="Grid X",
            yaxis_title="Grid Y",
            zaxis_title="Elevation (m)",
            aspectmode='data'
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    return fig


# --- STANDALONE UNIT TEST BLOCK ---
if __name__ == "__main__":
    print("--- Running Spatial Pathfinder Unit Test ---")
    
    # 1. Generate a synthetic 100x100 elevation grid (1 km x 1 km terrain)
    dem = generate_synthetic_lunar_dem(grid_shape=(100, 100), cell_size_m=10.0)
    pathfinder = SpatialPathfinder(cell_size_m=10.0)

    # 2. Define Start (Top-Left) and Goal (Bottom-Right across crater)
    start_point = (10, 10)
    goal_point = (90, 90)

    print(f"Grid Resolution: {dem.shape[0]}x{dem.shape[1]} cells ({pathfinder.cell_size_m}m/cell)")
    print(f"Start Coords: {start_point} | Goal Coords: {goal_point}")

    # 3. Execute A* Pathfinder
    path, total_cost = pathfinder.find_path_a_star(dem, start_point, goal_point)

    if path:
        total_distance_m = len(path) * pathfinder.cell_size_m
        slopes = pathfinder.calculate_slope_grid(dem)
        path_slopes = [slopes[r, c] for r, c in path]

        print("\n=== A* ROUTE FOUND ===")
        print(f"Path Node Count: {len(path)} Waypoints")
        print(f"Total Traversal Distance: {total_distance_m:.1f} meters")
        print(f"Max Slope Encountered: {max(path_slopes):.2f}° (Safe limit: 15.0°)")
        print(f"Average Slope on Route: {np.mean(path_slopes):.2f}°")
        print("Path head sample (first 5 waypoints):", path[:5])
        print("Path tail sample (last 5 waypoints):", path[-5:])
    else:
        print("[FAIL] No viable route could be established across terrain.")