###################################################################################################
# Module: plot.py
# Description: Plot spatial geometries, street networks, and routes
# License: MIT, see full license in LICENSE.txt
# Web: https://github.com/gboeing/osmnx
###################################################################################################

import time
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.collections import LineCollection
from descartes import PolygonPatch
from shapely.geometry import Polygon, MultiPolygon

from . import globals
from .utils import log
from .projection import project_graph
from .save_load import graph_to_gdfs
from .core import graph_from_address, graph_from_point, bbox_from_point

# folium is an optional dependency for the folium plotting functions
try:
    import folium
except ImportError as e:
    folium = None


def plot_shape(gdf, fc='#cbe0f0', ec='#999999', linewidth=1, alpha=1, figsize=(6,6), margin=0.02, axis_off=True):
    """
    Plot a GeoDataFrame of place boundary geometries.
    
    Parameters
    ----------
    gdf : GeoDataFrame
        the gdf containing the geometries to plot
    fc : string
        the facecolor for the polygons
    ec : string
        the edgecolor for the polygons
    linewidth : numeric
        the width of the polygon edge lines
    alpha : numeric
        the opacity
    figsize : tuple
        the size of the plotting figure
    margin : numeric
        the size of the figure margins
    axis_off : bool
        if True, disable the matplotlib axes display
    
    Returns
    -------
    fig, ax : tuple
    """
    # plot the geometries one at a time
    fig, ax = plt.subplots(figsize=figsize)
    for geometry in gdf['geometry'].tolist():
        if isinstance(geometry, (Polygon, MultiPolygon)):
            if isinstance(geometry, Polygon):
                geometry = MultiPolygon([geometry])
            for polygon in geometry:
                patch = PolygonPatch(polygon, fc=fc, ec=ec, linewidth=linewidth, alpha=alpha)
                ax.add_patch(patch)
        else:
            raise ValueError('All geometries in GeoDataFrame must be shapely Polygons or MultiPolygons')

    # adjust the axis margins and limits around the image and make axes equal-aspect
    west, south, east, north = gdf.unary_union.bounds
    margin_ns = (north - south) * margin
    margin_ew = (east - west) * margin
    ax.set_ylim((south - margin_ns, north + margin_ns))
    ax.set_xlim((west - margin_ew, east + margin_ew))
    ax.set_aspect(aspect='equal', adjustable='box')
    if axis_off:
        ax.axis('off')
    
    plt.show()
    return fig, ax


def get_edge_colors_by_attr(G, attr, num_bins=5, cmap='viridis', start=0, stop=1):
    """
    Get a list of edge colors by binning some continuous-variable attribute into quantiles.
    
    Parameters
    ----------
    G : networkx multidigraph
    attr : string
        the name of the continuous-variable attribute
    num_bins : int
        how many quantiles
    cmap : string
        name of a colormap
    start : float
        where to start in the colorspace
    stop : float
        where to end in the colorspace
    
    Returns
    -------
    list
    """
    bin_labels = range(num_bins)
    attr_values = pd.Series([data[attr] for u, v, key, data in G.edges(keys=True, data=True)])
    cats = pd.qcut(x=attr_values, q=num_bins, labels=bin_labels)
    color_list = [cm.get_cmap(cmap)(x) for x in np.linspace(start, stop, num_bins)]
    colors = [color_list[cat] for cat in cats]
    return colors
    
    
def save_and_show(fig, ax, save, show, close, filename, file_format, dpi, axis_off):
    """
    Save a figure to disk and show it, as specified.
    
    Parameters
    ----------
    fig : figure
    ax : axis
    save : bool
        whether to save the figure to disk or not
    show : bool
        whether to display the figure or not
    close : bool
        close the figure (only if show equals False) to prevent display
    filename : string
        the name of the file to save
    file_format : string
        the format of the file to save (e.g., 'jpg', 'png', 'svg')
    dpi : int
        the resolution of the image file if saving
    axis_off : bool
        if True matplotlib axis was turned off by plot_graph so constrain the saved figure's extent to the interior of the axis
    
    Returns
    -------
    fig, ax : tuple
    """
    # save the figure if specified
    if save:
        start_time = time.time()
        
        # create the save folder if it doesn't already exist
        if not os.path.exists(globals.imgs_folder):
            os.makedirs(globals.imgs_folder)
        path_filename = '{}/{}.{}'.format(globals.imgs_folder, filename, file_format)
        
        if file_format == 'svg':
            # if the file_format is svg, prep the fig/ax a bit for saving
            ax.axis('off')
            ax.set_position([0, 0, 1, 1])
            ax.patch.set_alpha(0.)
            fig.patch.set_alpha(0.)
            fig.savefig(path_filename, bbox_inches=0, format=file_format, facecolor=fig.get_facecolor(), transparent=True)
        else:
            if axis_off:
                # if axis is turned off, constrain the saved figure's extent to the interior of the axis
                extent = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
            else:
                extent = 'tight'
            fig.savefig(path_filename, dpi=dpi, bbox_inches=extent, format=file_format, facecolor=fig.get_facecolor(), transparent=True)
        log('Saved the figure to disk in {:,.2f} seconds'.format(time.time()-start_time))
    
    # show the figure if specified
    if show:
        start_time = time.time()
        plt.show()
        log('Showed the plot in {:,.2f} seconds'.format(time.time()-start_time))
    # if show=False, close the figure if close=True to prevent display
    elif close:
        plt.close()
        
    return fig, ax
    
    
def plot_graph(G, bbox=None, fig_height=6, fig_width=None, margin=0.02, axis_off=True, bgcolor='w',
               show=True, save=False, close=True, file_format='png', filename='temp', dpi=300, annotate=False,
               node_color='#66ccff', node_size=15, node_alpha=1, node_edgecolor='none', node_zorder=1,
               edge_color='#999999', edge_linewidth=1, edge_alpha=1, use_geom=True):
    """
    Plot a networkx spatial graph.
    
    Parameters
    ----------
    G : networkx multidigraph
    bbox : tuple
        bounding box as north,south,east,west - if None will calculate from spatial extents of data
    fig_height : int
        matplotlib figure height in inches
    fig_width : int
        matplotlib figure width in inches
    margin : float
        relative margin around the figure
    axis_off : bool
        if True turn off the matplotlib axis
    bgcolor : string
        the background color of the figure and axis
    show : bool
        if True, show the figure
    save : bool
        if True, save the figure as an image file to disk
    close : bool
        close the figure (only if show equals False) to prevent display
    file_format : string
        the format of the file to save (e.g., 'jpg', 'png', 'svg')
    filename : string
        the name of the file if saving
    dpi : int
        the resolution of the image file if saving
    annotate : bool
        if True, annotate the nodes in the figure
    node_color : string
        the color of the nodes
    node_size : int
        the size of the nodes
    node_alpha : float
        the opacity of the nodes
    node_edgecolor : string
        the color of the node's marker's border
    node_zorder : int
        zorder to plot nodes, edges are always 2, so make node_zorder 1 to plot nodes beneath them or 3 to plot nodes atop them
    edge_color : string
        the color of the edges' lines
    edge_linewidth : float
        the width of the edges' lines
    edge_alpha : float
        the opacity of the edges' lines
    use_geom : bool
        if True, use the spatial geometry attribute of the edges to draw geographically accurate edges, rather than just lines straight from node to node
    
    Returns
    -------
    fig, ax : tuple
    """
    
    log('Begin plotting the graph...')
    node_Xs = [float(node['x']) for node in G.node.values()]
    node_Ys = [float(node['y']) for node in G.node.values()]
    
    # get north, south, east, west values either from bbox parameter or from the spatial extent of the edges' geometries
    if bbox is None:
        edges = graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)
        west, south, east, north = edges.total_bounds
    else:
        north, south, east, west = bbox
    
    # if caller did not pass in a fig_width, calculate it proportionately from the fig_height and bounding box aspect ratio
    bbox_aspect_ratio = (north-south)/(east-west)
    if fig_width is None:
        fig_width = fig_height / bbox_aspect_ratio
    
    # create the figure and axis
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), facecolor=bgcolor)
    ax.set_facecolor(bgcolor)
    
    # draw the edges as lines from node to node
    start_time = time.time()
    lines = []
    for u, v, key, data in G.edges(keys=True, data=True):
        if 'geometry' in data and use_geom:
            # if it has a geometry attribute (a list of line segments), add them to the list of lines to plot
            xs, ys = data['geometry'].xy
            lines.append(list(zip(xs, ys)))
        else:
            # if it doesn't have a geometry attribute, the edge is a straight line from node to node
            x1 = G.node[u]['x']
            y1 = G.node[u]['y']
            x2 = G.node[v]['x']
            y2 = G.node[v]['y']
            line = [(x1, y1), (x2, y2)]
            lines.append(line)
    
    # add the lines to the axis as a linecollection
    lc = LineCollection(lines, colors=edge_color, linewidths=edge_linewidth, alpha=edge_alpha, zorder=2)
    ax.add_collection(lc)
    log('Drew the graph edges in {:,.2f} seconds'.format(time.time()-start_time))
    
    # scatter plot the nodes
    ax.scatter(node_Xs, node_Ys, s=node_size, c=node_color, alpha=node_alpha, edgecolor=node_edgecolor, zorder=node_zorder)
    
    # set the extent of the figure
    margin_ns = (north - south) * margin
    margin_ew = (east - west) * margin
    ax.set_ylim((south - margin_ns, north + margin_ns))
    ax.set_xlim((west - margin_ew, east + margin_ew))
    
    # configure axis appearance
    ax.get_xaxis().get_major_formatter().set_useOffset(False)
    ax.get_yaxis().get_major_formatter().set_useOffset(False)
    
    # if axis_off, turn off the axis display set the margins to zero and point the ticks in so there's no space around the plot
    if axis_off:
        ax.axis('off')
        ax.margins(0)
        ax.tick_params(which='both', direction='in')
        fig.canvas.draw()
    
    # annotate the axis with node IDs if annotate=True
    if annotate:
        for node, data in G.nodes(data=True):
            ax.annotate(node, xy=(data['x'], data['y']))
            
    # save and show the figure as specified
    fig, ax = save_and_show(fig, ax, save, show, close, filename, file_format, dpi, axis_off)
    return fig, ax


def plot_graph_route(G, route, bbox=None, fig_height=6, fig_width=None, margin=0.02, bgcolor='w',
                     axis_off=True, show=True, save=False, close=True, file_format='png', filename='temp', dpi=300, annotate=False,
                     node_color='#999999', node_size=15, node_alpha=1, node_edgecolor='none', node_zorder=1,
                     edge_color='#999999', edge_linewidth=1, edge_alpha=1, use_geom=True,
                     origin_point=None, destination_point=None,
                     route_color='r', route_linewidth=4, route_alpha=0.5, orig_dest_node_alpha=0.5,
                     orig_dest_node_size=100, orig_dest_node_color='r', orig_dest_point_color='b'):
    """
    Plot a route along a networkx spatial graph.
    
    Parameters
    ----------
    G : networkx multidigraph
    route : list
        the route as a list of nodes
    bbox : tuple
        bounding box as north,south,east,west - if None will calculate from spatial extents of data
    fig_height : int
        matplotlib figure height in inches
    fig_width : int
        matplotlib figure width in inches
    margin : float
        relative margin around the figure
    axis_off : bool
        if True turn off the matplotlib axis
    bgcolor : string
        the background color of the figure and axis
    show : bool
        if True, show the figure
    save : bool
        if True, save the figure as an image file to disk
    close : bool
        close the figure (only if show equals False) to prevent display
    file_format : string
        the format of the file to save (e.g., 'jpg', 'png', 'svg')
    filename : string
        the name of the file if saving
    dpi : int
        the resolution of the image file if saving
    annotate : bool
        if True, annotate the nodes in the figure
    node_color : string
        the color of the nodes
    node_size : int
        the size of the nodes
    node_alpha : float
        the opacity of the nodes
    node_edgecolor : string
        the color of the node's marker's border
    node_zorder : int
        zorder to plot nodes, edges are always 2, so make node_zorder 1 to plot nodes beneath them or 3 to plot nodes atop them
    edge_color : string
        the color of the edges' lines
    edge_linewidth : float
        the width of the edges' lines
    edge_alpha : float
        the opacity of the edges' lines
    use_geom : bool
        if True, use the spatial geometry attribute of the edges to draw geographically accurate edges, rather than just lines straight from node to node
    origin_point : tuple
        optional, an origin (lat, lon) point to plot instead of the origin node
    destination_point : tuple
        optional, a destination (lat, lon) point to plot instead of the destination node
    route_color : string
        the color of the route
    route_linewidth : int
        the width of the route line
    route_alpha : float
        the opacity of the route line
    orig_dest_node_alpha : float
        the opacity of the origin and destination nodes
    orig_dest_node_size : int
        the size of the origin and destination nodes
    orig_dest_node_color : string
        the color of the origin and destination nodes
    orig_dest_point_color : string
        the color of the origin and destination points if being plotted instead of nodes
    
    Returns
    -------
    fig, ax : tuple
    """
    
    # plot the graph but not the route
    fig, ax = plot_graph(G, bbox=bbox, fig_height=fig_height, fig_width=fig_width, margin=margin, axis_off=axis_off, bgcolor=bgcolor,
                         show=False, save=False, close=False, filename=filename, dpi=dpi, annotate=annotate,
                         node_color=node_color, node_size=node_size, node_alpha=node_alpha, node_edgecolor=node_edgecolor, node_zorder=node_zorder,
                         edge_color=edge_color, edge_linewidth=edge_linewidth, edge_alpha=edge_alpha, use_geom=use_geom)
    
    # the origin and destination nodes are the first and last nodes in the route
    origin_node = route[0]
    destination_node = route[-1]
        
    if origin_point is None or destination_point is None:
        # if caller didn't pass points, use the first and last node in route as origin/destination    
        origin_destination_lats = (G.node[origin_node]['y'], G.node[destination_node]['y'])
        origin_destination_lons = (G.node[origin_node]['x'], G.node[destination_node]['x'])
    else:
        # otherwise, use the passed points as origin/destination
        origin_destination_lats = (origin_point[0], destination_point[0])
        origin_destination_lons = (origin_point[1], destination_point[1])
        orig_dest_node_color = orig_dest_point_color
    
    # scatter the origin and destination points
    ax.scatter(origin_destination_lons, origin_destination_lats, s=orig_dest_node_size, 
               c=orig_dest_node_color, alpha=orig_dest_node_alpha, edgecolor=node_edgecolor, zorder=4)
    
    # plot the route lines
    edge_nodes = list(zip(route[:-1], route[1:]))
    lines = []
    for u, v in edge_nodes:
        # if there are parallel edges, select the shortest in length
        data = min([data for data in G.edge[u][v].values()], key=lambda x: x['length'])
        
        # if it has a geometry attribute (ie, a list of line segments)
        if 'geometry' in data and use_geom:
            # add them to the list of lines to plot
            xs, ys = data['geometry'].xy
            lines.append(list(zip(xs, ys)))
        else:
            # if it doesn't have a geometry attribute, the edge is a straight line from node to node
            x1 = G.node[u]['x']
            y1 = G.node[u]['y']
            x2 = G.node[v]['x']
            y2 = G.node[v]['y']
            line = [(x1, y1), (x2, y2)]
            lines.append(line)
    
    # add the lines to the axis as a linecollection    
    lc = LineCollection(lines, colors=route_color, linewidths=route_linewidth, alpha=route_alpha, zorder=3)
    ax.add_collection(lc)
    
    # save and show the figure as specified
    fig, ax = save_and_show(fig, ax, save, show, close, filename, file_format, dpi, axis_off)
    return fig, ax
    
    
def make_folium_polyline(edge, edge_color, edge_width, edge_opacity, popup_attribute=None):
    
    """
    Turn a row from the gdf_edges GeoDataFrame into a folium PolyLine with attributes.
    
    Parameters
    ----------
    edge : GeoSeries
        a row from the gdf_edges GeoDataFrame
    edge_color : string
        color of the edge lines
    edge_width : numeric
        width of the edge lines
    edge_opacity : numeric
        opacity of the edge lines
    popup_attribute : string
        edge attribute to display in a pop-up when an edge is clicked, if None, no popup
    
    Returns
    -------
    pl : folium.PolyLine
    """
    
    # check if we were able to import folium successfully
    if not folium:
        raise ImportError('The folium package must be installed to use this optional feature.')
    
    # locations is a list of points for the polyline
    locations = list(edge['geometry'].coords)
    
    # if popup_attribute is None, then create no pop-up
    if popup_attribute is None:
        popup = None        
    else:
        # folium doesn't interpret html in the html argument (weird), so can't do newlines without an iframe
        popup_text = str(edge[popup_attribute])
        popup = folium.Popup(html=popup_text)
    
    # create a folium polyline with attributes
    pl = folium.PolyLine(locations=locations, popup=popup, latlon=False, 
                         color=edge_color, weight=edge_width, opacity=edge_opacity)
    return pl
    

def plot_graph_folium(G, graph_map=None, popup_attribute=None, tiles='cartodbpositron', zoom=1, fit_bounds=True, 
                      edge_color='#333333', edge_width=5, edge_opacity=1):
    """
    Plot a graph on an interactive folium web map.
    
    Note that anything larger than a small city can take a long time to plot and create a large web map
    file that is very slow to load as JavaScript.
    
    Parameters
    ----------
    G : networkx multidigraph
    graph_map : folium.folium.Map
        if not None, plot the graph on this preexisting folium map object
    popup_attribute : string
        edge attribute to display in a pop-up when an edge is clicked
    tiles : string
        name of a folium tileset
    zoom : int
        initial zoom level for the map
    fit_bounds : bool
        if True, fit the map to the boundaries of the route's edges
    edge_color : string
        color of the edge lines
    edge_width : numeric
        width of the edge lines
    edge_opacity : numeric
        opacity of the edge lines
    
    Returns
    -------
    graph_map : folium.folium.Map
    """
    
    # check if we were able to import folium successfully
    if not folium:
        raise ImportError('The folium package must be installed to use this optional feature.')
    
    # create gdf of the graph edges
    gdf_edges = graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)
    
    # get graph centroid
    x, y = gdf_edges.unary_union.centroid.xy
    graph_centroid = (y[0], x[0])
    
    # create the folium web map if one wasn't passed-in
    if graph_map is None:
        graph_map = folium.Map(location=graph_centroid, zoom_start=zoom, tiles=tiles)
    
    # add each graph edge to the map
    for _, row in gdf_edges.iterrows():
        pl = make_folium_polyline(edge=row, edge_color=edge_color, edge_width=edge_width, 
                                  edge_opacity=edge_opacity, popup_attribute=popup_attribute)
        pl.add_to(graph_map)
    
    # if fit_bounds is True, fit the map to the bounds of the route by passing list of lat-lng points as [southwest, northeast]
    if fit_bounds:
        tb = gdf_edges.total_bounds
        bounds = [(tb[1], tb[0]), (tb[3], tb[2])]
        graph_map.fit_bounds(bounds)
        
    return graph_map    
    
    
def plot_route_folium(G, route, route_map=None, popup_attribute=None, tiles='cartodbpositron', zoom=1, fit_bounds=True, 
                      route_color='#cc0000', route_width=5, route_opacity=1):
    """
    Plot a route on an interactive folium web map.
    
    Parameters
    ----------
    G : networkx multidigraph
    route : list
        the route as a list of nodes
    route_map : folium.folium.Map
        if not None, plot the route on this preexisting folium map object
    popup_attribute : string
        edge attribute to display in a pop-up when an edge is clicked
    tiles : string
        name of a folium tileset
    zoom : int
        initial zoom level for the map
    fit_bounds : bool
        if True, fit the map to the boundaries of the route's edges
    route_color : string
        color of the route's line
    route_width : numeric
        width of the route's line
    route_opacity : numeric
        opacity of the route lines
    
    Returns
    -------
    route_map : folium.folium.Map
    """
    
    # check if we were able to import folium successfully
    if not folium:
        raise ImportError('The folium package must be installed to use this optional feature.')
    
    # create gdf of the route edges
    gdf_edges = graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)
    route_nodes = list(zip(route[:-1], route[1:]))
    index = [gdf_edges[(gdf_edges['u']==u) & (gdf_edges['v']==v)].index[0] for u, v in route_nodes]
    gdf_route_edges = gdf_edges.loc[index]
    
    # get route centroid
    x, y = gdf_route_edges.unary_union.centroid.xy
    route_centroid = (y[0], x[0])
    
    # create the folium web map if one wasn't passed-in
    if route_map is None:
        route_map = folium.Map(location=route_centroid, zoom_start=zoom, tiles=tiles)
    
    # add each route edge to the map
    for _, row in gdf_route_edges.iterrows():
        pl = make_folium_polyline(edge=row, edge_color=route_color, edge_width=route_width, 
                                  edge_opacity=route_opacity, popup_attribute=popup_attribute)
        pl.add_to(route_map)
    
    # if fit_bounds is True, fit the map to the bounds of the route by passing list of lat-lng points as [southwest, northeast]
    if fit_bounds:
        tb = gdf_route_edges.total_bounds
        bounds = [(tb[1], tb[0]), (tb[3], tb[2])]
        route_map.fit_bounds(bounds)
    
    return route_map
    
    
def plot_figure_ground(address=None, point=None, dist=805, network_type='drive_service',
                       street_widths=None, default_width=4, fig_length=8, edge_color='w', bgcolor='#333333',
                       filename=None, file_format='png', show=False, save=True, close=True, dpi=300):
    """
    Plot a figure-ground diagram of a street network, defaulting to one square mile.
    
    Parameters
    ----------
    address : string
        the address to geocode as the center point
    point : tuple
        the center point if address is not passed
    dist : numeric
        how many meters to extend north, south, east, and west from the center point
    network_type : string
        what type of network to get
    street_widths : dict
        where keys are street types and values are widths to plot in pixels
    default_width : numeric
        the default street width in pixels for any street type not found in street_widths dict
    fig_length : numeric
        the height and width of this square diagram
    edge_color : string
        the color of the streets
    bgcolor : string
        the color of the background
    filename : string
        filename to save the image as
    file_format : string
        the format of the file to save (e.g., 'jpg', 'png', 'svg')
    show : bool
        if True, show the figure
    save : bool 
        if True, save the figure as an image file to disk
    close : bool
        close the figure (only if show equals False) to prevent display
    dpi : int
        the resolution of the image file if saving
    
    Returns
    -------
    fig, ax : tuple
    """
    
    # get the network by either address or point, whichever was passed-in, using a distance multiplier to make sure we get more than enough network
    multiplier = 1.2
    if not address is None:
        G, point = graph_from_address(address, distance=dist*multiplier, distance_type='bbox', network_type=network_type, 
                                      truncate_by_edge=True, return_coords=True)
    elif not point is None:
        G = graph_from_point(point, distance=dist*multiplier, distance_type='bbox', network_type=network_type, 
                             truncate_by_edge=True)
    else:
        raise ValueError('You must pass an address or lat-long point.')
    
    # project the network to UTM
    G = project_graph(G)
    
    # if user did not pass in custom street widths, create a dict of default values
    if street_widths is None:
        street_widths = {'footway' : 1.5,
                         'steps' : 1.5,
                         'pedestrian' : 1.5,
                         'service' : 1.5,
                         'path' : 1.5,
                         'track' : 1.5,
                         'motorway' : 6}
    
    # for each network edge, get a linewidth according to street type (the OSM 'highway' value)
    edge_linewidths = []
    for u, v, key, data in G.edges(keys=True, data=True):
        street_type = data['highway'][0] if isinstance(data['highway'], list) else data['highway']
        if street_type in street_widths:
            edge_linewidths.append(street_widths[street_type])
        else:
            edge_linewidths.append(default_width)
    
    # define the spatial extents of the plotting figure to make it square, in projected units, and cropped to the desired area
    bbox_proj = bbox_from_point(point, dist, project_utm=True)
    
    # create a filename if one was not passed
    if filename is None and save:
        filename = 'figure_ground_{}_{}'.format(point, network_type)
    
    # plot the figure
    fig, ax = plot_graph(G, bbox=bbox_proj, fig_height=fig_length, margin=0, node_size=0, 
                         edge_linewidth=edge_linewidths, edge_color=edge_color, bgcolor=bgcolor, 
                         show=show, save=save, close=close, filename=filename, file_format=file_format, dpi=dpi)
    
    # make everything square
    ax.set_aspect('equal')
    fig.canvas.draw()
    
    return fig, ax
    
    