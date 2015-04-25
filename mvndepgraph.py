"""
Makes use of Maven to generate a DOT file of maven project dependencies
"""
import sys, pydot, optparse, re, json 


class NodeStyleRule(object):
    def __init__(self, match_pattern, style_attributes): 
        self.style_attributes=style_attributes
        self.match_pattern=re.compile(match_pattern)

    @staticmethod
    def globalRule(style_attributes):
        return NodeStyleRule('^.*$', style_attributes)

    @staticmethod
    def from_json(json_obj):
        """
        Takes JSON object in the form:

        [
          {"pattern": "^.*site2.keyword.*$", "attributes": {"fillcolor": "#ff0000", "style":"filled"}},
          {"pattern": "^.*redirectcontroller.*$", "attributes": {"fillcolor": "#00ff00", "style":"filled"}}
        ]

        """
        rules = []

        for x in json_obj:
            rules.append(NodeStyleRule(x['pattern'], x['attributes']))

        return rules


    def apply(self, graph, edge):
        self.apply_node(graph, edge.get_source())
        self.apply_node(graph, edge.get_destination())


    def apply_node(self, graph, node_name):

        if self.match_pattern.match(node_name):

            # look for the node in the graph -- 
            # it may not exist if the graph is 
            # composed only of edges.
            n = graph.get_node(node_name)

            # if no node, create one so you can
            # hang your styling directives
            if not n:
                n = [pydot.Node(node_name)]
                graph.add_node(n[0])

            # actually impose the styles    
            self.copy_attributes(n[0])
        

    def copy_attributes(self, node):
        for a in self.style_attributes:
            node.set(a, self.style_attributes[a])
        




class SquashVersionRule(object):

    MVN_VERSION_POSITION=3
    
    def apply(self, graph, edge):

        # create a new edge with the version removed from the node names
        old_src, old_dst = (edge.get_source(), edge.get_destination()) 
        new_edge = pydot.Edge(self.squash_version(old_src), self.squash_version(old_dst))

        # tag the target of the edge's version
        self.tag_version(graph, old_dst)

        # remove old and add new
        graph.del_edge(old_src, old_dst)
        graph.add_edge(new_edge)

    def tag_version(self, graph, version_name):

        no_version_name = self.squash_version(version_name)

        nlist = graph.get_node(no_version_name)

        # if no node, create one so you can
        # hang your styling directives
        if not nlist:
            n = pydot.Node(no_version_name)
            graph.add_node(n)        
        else:
            n = nlist[0]

        versions = n.get('versions')
        if not versions:
            versions = set([])
            n.set('versions', versions)

        versions.add(version_name)

    def squash_version(self, value):
        # we slap the quote back on at the end, because the quotes 
        # are actually a part of the string value of the node name :-(
        new_version = (':'.join(value.split(':')[:SquashVersionRule.MVN_VERSION_POSITION])) + '"'
        return new_version

    @staticmethod
    def clean_version_tag(node):
        """
        remove the 'versions' attribute otherwise dot will barf, and 
        mark nodes with more than one version by changing the node shape
        """
        versions = node.get('versions')
        if versions:
            if len(versions) > 1:
                node.set('shape', 'tripleoctagon')
                # for nodes we didn't otherwise style, if they don't 
                # get styled, the node shape will also not change
                if not node.get('style'):
                    node.set('style', 'filled')
                    node.set('fillcolor', GraphProcessor.DEFAULT_COLORS['conflict'])
                
        # we don't have a good way of actually removing the attribute, so we set it to a blank string
        node.set('versions', " ")
        



class GraphProcessor(object):

    DEFAULT_COLORS= {
        'intersect': '#00FF00',
        'non_intersect_list': [ '#ccffff', '#FF99FF',  '#CCFF66', '#FF9966', '#6600FF', '#FF0033', '#FFFF00', '#CCCCCC'],
        'highlight': '#FF66FF',
        'conflict': '#ffffff'
    }

    def __init__(self, style_rules=None):
        self.style_rules=[]
        if style_rules:
            self.style_rules.extend(style_rules)

    
    @staticmethod
    def intersecting_nodes(graphs):

        # list of nodes per graph
        node_sets=[]
        for x in graphs:
            nset=set([])
            for y in x.get_edges():
                nset.add(y.get_source())
                nset.add(y.get_destination())
            node_sets.append(nset)

        return node_sets, reduce(lambda x, y: x.intersection(y) , node_sets, node_sets[0])
    
    @staticmethod
    def non_intersecting_nodes_per_graph(graphs, node_sets):
    
        non_intersect = {}
        for i in range(0, len(graphs)):

            gname = graphs[i].get_name()
            self_set = node_sets[i]

            # get the node sets minus yourself
            minus_self_set = node_sets[0:i] + node_sets[i+1:]
            minus_self_set.insert(i, set([]))
        
            non_intersect[gname] = reduce(lambda x, y: x.difference(y) , minus_self_set, self_set)
    
        return non_intersect

    @staticmethod
    def merge_graphs(graphs):

        merged = pydot.Dot()

        for g in graphs:

            # copy all the edges in to the merged graph
            for e in g.get_edges():
                merged.add_edge(pydot.Edge(e.get_source(), e.get_destination()))
            
            # copy the nodes in too, but specifically merge their 'versions' attributes
            for n in g.get_nodes():

                nn = pydot.Node(n.get_name(), None, **n.get_attributes())
                mn = merged.get_node(n.get_name())

                if mn:
                    mversions = mn[0].get('versions')
                    nversions = nn.get('versions')
                    if mversions and nversions:
                        mversions.update(nversions)
                    elif nversions:
                        mn[0].set('versions', nversions)

                else:
                    merged.add_node(nn)


        return merged


    @staticmethod
    def do_squash_versions(graph):
        squash = SquashVersionRule()
        for e in graph.get_edges():
            squash.apply(graph, e)
    
            
    @staticmethod
    def maximum_input_graphs():
        # we're probably bound by ram before this, but this is our "logical" limit
        max_inputs = len(GraphProcessor.DEFAULT_COLORS['non_intersect_list'])
        return max_inputs


    def process_graphs(self, file_names, squash_versions=False, analyze=False):
    
        graphs = []
        for x in file_names:
            xg = pydot.graph_from_dot_file(x)
            graphs.append(xg)
        
        final_graph = graphs[0]

        if len(graphs) > 1:

            if squash_versions:
                for g in graphs:
                    GraphProcessor.do_squash_versions(g)
        
            final_graph = GraphProcessor.merge_graphs(graphs)    

            # we're a little broken here, because the version squashing 
            # plus merging does some implicit analysis of version conflicts
            if analyze:

                per_graph_node_sets, intersection = GraphProcessor.intersecting_nodes(graphs)

                style=NodeStyleRule.globalRule({'fillcolor': GraphProcessor.DEFAULT_COLORS['intersect'], 'style':'filled'}) 

                for x in intersection:        
                    style.apply_node(final_graph, x)

                non_intersect = GraphProcessor.non_intersecting_nodes_per_graph(graphs, per_graph_node_sets)

                for x in non_intersect:

                    color = GraphProcessor.DEFAULT_COLORS['non_intersect_list'].pop(0)
                    style = NodeStyleRule.globalRule({'fillcolor':color, 'style':'filled'})

                    for y in non_intersect[x]:
                        style.apply_node(final_graph, y)


        if squash_versions:
            # necessary because we wedged a non-standard
            # attribute into the nodes marking their versions
            for n in final_graph.get_nodes():
                SquashVersionRule.clean_version_tag(n)

        for rule in self.style_rules:
            for e in final_graph.get_edges():
                rule.apply(final_graph, e)

        # otherwise it's unreadable
        final_graph.set('rankdir', 'LR')

        return final_graph



    
if __name__ == '__main__':

    op = optparse.OptionParser(usage="usage: %prog [options] INPUT_FILE_NAMES")
    op.add_option("-o", dest="output_file", default=None, help="Output file name (stdout by default)")
    op.add_option("--squash-version", dest="squash_version", action="store_true", default=False, help="Remove versions from dependencies (disabled by default, and applicable only to multiple graphs)")
    op.add_option("--analyze", dest="analyze", action="store_true", default=False, help="Analyze intersections, differences, etc (disabled by default, and applicable only to multiple graphs)")
    op.add_option("--format", dest="format", default='raw', help="Output format (raw by default).  Any output format supported by dot.  Must be used in conjunction with -o option.")
    op.add_option("--highlight-pattern", dest="highlight_pattern", default=None, help="Regular expression that includes dependencies to highlight.  Must be a full match.  Applied after other colorings.")
    op.add_option("--styles", dest="styles_file", default=None, help="Path to JSON file containing style rules. See NodeStyleRule.from_json for more details.")

    (options, args) = op.parse_args()

    max_inputs = GraphProcessor.maximum_input_graphs()

    if not args:
        op.error("You must specify at least one input file. Use -h option to display help message.")
    elif len(args) > max_inputs:
        op.error("You cannot specify more than %d input files.  Use -h option to display help message." % max_inputs)
    
    input_file_names = args
    output_file_name = options.output_file

    if len(input_file_names) < 2 and options.squash_version:
        op.error("--squash-version is not effective for a single input file.  Use -h to display help message.")

    if len(input_file_names) < 2 and options.analyze:
        op.error("--analyze is not effective for a single input file.  Use -h to display help message.")


    gp = GraphProcessor()

    if options.styles_file:
        style_f = open(options.styles_file, 'r')
        style_json = json.load(style_f)
        rules = NodeStyleRule.from_json(style_json)
        gp.style_rules.extend(rules)

    if options.highlight_pattern:
        gp.style_rules.append(NodeStyleRule(options.highlight_pattern, {'fillcolor': GraphProcessor.DEFAULT_COLORS['highlight'], 'style':'filled'}))

    g = gp.process_graphs(input_file_names, options.squash_version, options.analyze)

    if not options.output_file:
        print(g.to_string())
    else:
        g.write(output_file_name, format=options.format)
    
