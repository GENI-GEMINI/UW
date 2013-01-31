"""
Provides RSpec3Decoder class

@author: Ahmed El-Hassany
@author: fernandes
"""

import json
import re
import sys
import uuid
from urllib import unquote, quote
from lxml import etree

class UNISDecoderException(Exception):
    """The default exception raise by UNIS decoders"""
    pass

class UNISDecoder(object):
    """Abstract class for UNIS decoders."""
    
    SCHEMAS = {
        'networkresource': 'http://unis.incntre.iu.edu/schema/20120709/networkresource#',
        'node': 'http://unis.incntre.iu.edu/schema/20120709/node#',
        'domain': 'http://unis.incntre.iu.edu/schema/20120709/domain#',
        'topology': 'http://unis.incntre.iu.edu/schema/20120709/topology#',
        'port': 'http://unis.incntre.iu.edu/schema/20120709/port#',
        'link': 'http://unis.incntre.iu.edu/schema/20120709/link#',
        'network': 'http://unis.incntre.iu.edu/schema/20120709/network#',
        'blipp': 'http://unis.incntre.iu.edu/schema/20120709/blipp#',
        'metadata': 'http://unis.incntre.iu.edu/schema/20120709/metadata#',
    }
    
    def __init__(self):
        self._guid = uuid.uuid1()
    
    def encode(self, tree, **kwargs):
        """Abstract method."""
        raise NotImplementedError
    
    def _encode_ignore(self, doc, out, **kwargs):
        """Just log Ignore an element."""
        return
    
    def _parse_xml_bool(self, xml_bool):
        clean = xml_bool.strip().lower()
        map_bool = {"true": True, "false": False, "1": True, "0": False}
        if clean not in map_bool:
            return xml_bool
        else:
            return map_bool[clean]
    
    @staticmethod
    def is_valid_ipv4(ip):
        """Validates IPv4 addresses."""
        
        pattern = re.compile(r"""
            ^
            (?:
              # Dotted variants:
              (?:
                # Decimal 1-255 (no leading 0's)
                [3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}
              |
                0x0*[0-9a-f]{1,2}  # Hexadecimal 0x0 - 0xFF (possible leading 0's)
              |
                0+[1-3]?[0-7]{0,2} # Octal 0 - 0377 (possible leading 0's)
              )
              (?:                  # Repeat 0-3 times, separated by a dot
                \.
                (?:
                  [3-9]\d?|2(?:5[0-5]|[0-4]?\d)?|1\d{0,2}
                |
                  0x0*[0-9a-f]{1,2}
                |
                  0+[1-3]?[0-7]{0,2}
                )
              ){0,3}
            |
              0x0*[0-9a-f]{1,8}    # Hexadecimal notation, 0x0 - 0xffffffff
            |
              0+[0-3]?[0-7]{0,10}  # Octal notation, 0 - 037777777777
            |
              # Decimal notation, 1-4294967295:
              429496729[0-5]|42949672[0-8]\d|4294967[01]\d\d|429496[0-6]\d{3}|
              42949[0-5]\d{4}|4294[0-8]\d{5}|429[0-3]\d{6}|42[0-8]\d{7}|
              4[01]\d{8}|[1-3]\d{0,9}|[4-9]\d{0,8}
            )
            $
        """, re.VERBOSE | re.IGNORECASE)
        return pattern.match(ip) is not None

    @staticmethod
    def is_valid_ipv6(ip):
        """Validates IPv6 addresses."""
        
        pattern = re.compile(r"""
            ^
            \s*                         # Leading whitespace
            (?!.*::.*::)                # Only a single whildcard allowed
            (?:(?!:)|:(?=:))            # Colon iff it would be part of a wildcard
            (?:                         # Repeat 6 times:
                [0-9a-f]{0,4}           #  A group of at most four hexadecimal digits
                (?:(?<=::)|(?<!::):)    #  Colon unless preceeded by wildcard
            ){6}                        #
            (?:                         # Either
                [0-9a-f]{0,4}           #   Another group
                (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
                [0-9a-f]{0,4}           #   Last group
                (?: (?<=::)             #   Colon iff preceeded by exacly one colon
                 |  (?<!:)              #
                 |  (?<=:) (?<!::) :    #
                 )                      # OR
             |                          #   A v4 address with NO leading zeros
                (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
                (?: \.
                    (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
                ){3}
            )
            \s*                         # Trailing whitespace
            $
        """, re.VERBOSE | re.IGNORECASE | re.DOTALL)
        return pattern.match(ip) is not None

    
class RSpec3Decoder(UNISDecoder):
    """Decodes RSpecV3 to UNIS format."""
    
    rspec3 = "http://www.geni.net/resources/rspec/3"
    gemini = "http://geni.net/resources/rspec/ext/gemini/1"
    
    RSpecADV = "advertisement"
    RSpecRequest = "request"
    RSpecManifest = "manifest"
    
    def __init__(self):
        super(RSpec3Decoder, self).__init__()
        self._parent_collection = {}
        self._tree = None
        self._root = None
        self._jsonpointer_path = "#/"
        self._jsonpath_cache = {}
        self._urn_cache = {}
        self._component_id_cache = {}
        self._sliver_id_cache = {}
        self.geni_ns = "geni"
        self._ignored_namespaces = [
            "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/",
            "http://www.protogeni.net/resources/rspec/ext/emulab/1",
            "http://www.protogeni.net/resources/rspec/ext/flack/1",
            "http://www.protogeni.net/resources/rspec/ext/client/1",
        ]
        # Resolving jsonpath is expensive operation
        # This cache keeps track of jsonpath used to replaced in the end
        # with jsonpointers
        self._subsitution_cache = {}
        
        self._handlers = {
            "{%s}%s" % (RSpec3Decoder.rspec3, "rspec") : self._encode_rspec,
            "{%s}%s" % (RSpec3Decoder.rspec3, "node") : self._encode_rspec_node,
            "{%s}%s" % (RSpec3Decoder.rspec3, "location") : self._encode_rspec_location,
            "{%s}%s" % (RSpec3Decoder.rspec3, "hardware_type") : self._encode_rspec_hardware_type,
            "{%s}%s" % (RSpec3Decoder.rspec3, "interface") : self._encode_rspec_interface,
            "{%s}%s" % (RSpec3Decoder.rspec3, "available") : self._encode_rspec_available,
            "{%s}%s" % (RSpec3Decoder.rspec3, "sliver_type") : self._encode_rspec_sliver_type,
            "{%s}%s" % (RSpec3Decoder.rspec3, "disk_image") : self._encode_rspec_disk_image,
            "{%s}%s" % (RSpec3Decoder.rspec3, "relation") : self._encode_rspec_relation,
            "{%s}%s" % (RSpec3Decoder.rspec3, "link") : self._encode_rspec_link,
            "{%s}%s" % (RSpec3Decoder.rspec3, "link_type") : self._encode_rspec_link_type,
            "{%s}%s" % (RSpec3Decoder.rspec3, "component_manager") : self._encode_rspec_component_manager,
            "{%s}%s" % (RSpec3Decoder.rspec3, "interface_ref") : self._encode_rspec_interface_ref,
            "{%s}%s" % (RSpec3Decoder.rspec3, "property") : self._encode_rspec_property,
            "{%s}%s" % (RSpec3Decoder.rspec3, "host") : self._encode_rspec_host,
            "{%s}%s" % (RSpec3Decoder.rspec3, "ip") : self._encode_rspec_ip,
            "{%s}%s" % (RSpec3Decoder.gemini, "node") : self._encode_gemini_node,
            "{%s}%s" % (RSpec3Decoder.gemini, "monitor_urn") : self._encode_gemini_monitor_urn,
        }
    
    def _encode_children(self, doc, out, **kwargs):
        """Iterates over the all child nodes and process and call the approperiate
        handler for each one."""
        for child in doc.iterchildren():
            if child.tag is etree.Comment:
                continue
            if child.nsmap.get(child.prefix, None) in self._ignored_namespaces:
                continue
            if child.tag in self._handlers:
                self._handlers[child.tag](child, out, **kwargs)
            else:
                pass
                #sys.stderr.write("No handler for: %s\n" % child.tag)
    @staticmethod
    def rspec_create_urn(component_id):
        return unquote(component_id).strip()
    
    def _refactor_default_xmlns(self, tree):
        """
        Change the RSpec from the default namespace to an explicit namespace.
        This will make xpath works!
        """
        exclude_ns = ""
        exclude_prefixes = ""
        for x in range(len(self._ignored_namespaces)):
            exclude_ns += 'xmlns:ns%d="%s"\n' % (x, self._ignored_namespaces[x])
            exclude_prefixes +="ns%d " % x
        if exclude_ns != "":
            exclude_prefixes = 'exclude-result-prefixes="%s"\n' % exclude_prefixes 
            
            
        XSLT = """
        <xsl:stylesheet version="1.0" 
           xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
           xmlns="http://sample.com/s" 
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
           xmlns:xs="http://www.w3.org/2001/XMLSchema"
           %s
           %s
           xmlns:rspec="%s"
           >

           <xsl:output method="xml" encoding="UTF-8" indent="yes"/>
           
           <xsl:template match="/">
             <xsl:copy>
                <xsl:apply-templates select="@* | node()"/>
             </xsl:copy>              
           </xsl:template>
           
           <xsl:template match="*">
              <xsl:copy>
                <xsl:apply-templates select="@* | node()"/>
              </xsl:copy>
           </xsl:template>
           

           <xsl:template match="rspec:*">
              <xsl:element name="rspec:{local-name()}">
                 <xsl:apply-templates select="@* | node()"/>
              </xsl:element>
           </xsl:template>
           
           <xsl:template match="@*">
              <xsl:attribute name="{local-name()}">
                 <xsl:value-of select="."/>
              </xsl:attribute>
           </xsl:template>
        </xsl:stylesheet>
        """ % (exclude_ns, exclude_prefixes, RSpec3Decoder.rspec3)
        
        xslt_root = etree.XML(XSLT)
        transform = etree.XSLT(xslt_root)
        tree = transform(tree)
        return tree

    def encode(self, tree, slice_urn=None, **kwargs):
        out = {}
        tree = self._refactor_default_xmlns(tree)
        root = tree.getroot()
        self._tree = tree
        self._root = root
        self._parent_collection = out
        
        if root.tag in self._handlers:
            self._handlers[root.tag](root, out, collection=out,
                parent=out, slice_urn=slice_urn, **kwargs)
        else:
            pass
            #sys.stderr.write("No handler for: %s\n" % root.tag)
        
        sout = json.dumps(out)
        # This is an optimization hack to make every jsonpath a jsonpointer
        for urn, jpath in self._subsitution_cache.iteritems():
            if urn in self._jsonpath_cache:
                sout = sout.replace(jpath, self._jsonpath_cache[urn])
        out = json.loads(sout)
        
        return out
    
    def _encode_rspec(self, doc, out, **kwargs):
        assert isinstance(out, dict)
        assert doc.tag in ["{%s}rspec" % RSpec3Decoder.rspec3], \
            "Not valid element '%s'" % doc.tag
        
        if not self._parent_collection:
            self._parent_collection = out
            self._jsonpointer_path =  "#"
        # Parse GENI specific properties
        out["$schema"] = UNISDecoder.SCHEMAS["domain"]
        if "properties" not in out:
            out["properties"] = {}
        if self.geni_ns not in out["properties"]:
            out["properties"][self.geni_ns] = {}
        geni_props = out["properties"][self.geni_ns]
        attrib = dict(doc.attrib)
        # From XML schema
        attrib.pop('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', None)
        # From common.rnc
        generated = attrib.pop('generated', None)
        generated_by = attrib.pop('generated_by', None)
        expires = attrib.pop('expires', None)
        # From ad.rnc and request.rnc
        rspec_type = attrib.pop('type', "")
        rspec_type = rspec_type.strip()
        
        # Some validation of Inpu
        if rspec_type not in [RSpec3Decoder.RSpecADV, RSpec3Decoder.RSpecManifest]:
            raise UNISDecoderException("Unsupported rspec type '%s'" % rspec_type)
        
        if rspec_type == RSpec3Decoder.RSpecManifest and kwargs.get("slice_urn", None) is None:
            raise UNISDecoderException("slice_urn must be provided "
                "when decoding manifest.")
         
        if rspec_type == RSpec3Decoder.RSpecADV and kwargs.get("component_manager_id", None) is None:
            raise UNISDecoderException("component_manager_id must be "
                "provided when decoding advertisment rspec.")
        
        # Building GENI properties
        if generated is not None:
            geni_props['generated'] = generated.strip()
        if generated_by is not None:
            geni_props['generated_by'] = generated_by.strip()
        if expires is not None:
            geni_props['expires'] = expires.strip()
        if rspec_type is not None:
            geni_props['type'] = rspec_type.strip()
        kwargs.pop("parent", None)
        collection = kwargs.pop("collection", out)
        
         # Generating URN
        if rspec_type == RSpec3Decoder.RSpecManifest:
            slice_urn = kwargs.get("slice_urn", None)
            geni_props['slice_urn'] = slice_urn            
            out["urn"] = slice_urn
            slice_uuid = kwargs.get("slice_uuid")
            if slice_uuid is not None:
                geni_props['slice_uuid'] = slice_uuid
            out["id"] = self.geni_urn_to_id(slice_urn)
        elif rspec_type == RSpec3Decoder.RSpecADV:
            component_manager_id = kwargs.get("component_manager_id", None)            
            out["id"] = self.geni_urn_to_id(component_manager_id)
            out["urn"] = component_manager_id
        
        # Iterate children
        self._encode_children(doc, out, rspec_type=rspec_type,
            collection=collection, parent=out, **kwargs)
        
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
            
        return out
    
    def geni_urn_to_id(self, geni_id):
        return geni_id.replace('urn:publicid:IDN+', '').replace('+', '_')
    
    def _encode_rspec_node(self, doc, out, collection, **kwargs):
        assert isinstance(out, dict)
        assert doc.tag in [
            "{%s}node" % RSpec3Decoder.rspec3
        ], "Not valid element '%s'" % doc.tag
        node = {}
        node["$schema"] = UNISDecoder.SCHEMAS["node"]
        if "nodes" not in collection:
            collection["nodes"] = []
        
        # Parse GENI specific properties
        if "properties" not in node:
            node["properties"] = {}
        if self.geni_ns not in node["properties"]:
            node["properties"][self.geni_ns] = {}
        geni_props = node["properties"][self.geni_ns]
        attrib = dict(doc.attrib)
        # From common.rnc
        # From ad.rnc & request.rnc
        component_id = attrib.pop('component_id', None)
        component_manager_id = attrib.pop('component_manager_id', None)
        component_name = attrib.pop('component_name', None)
        # From request.rnc
        client_id = attrib.pop('client_id', None)
        exclusive = attrib.pop('exclusive', None)
        colocate = attrib.pop('colocate', None)
        # From manifest.rnc
        sliver_id = attrib.pop('sliver_id', None)
        
        if component_id is not None:
            geni_props['component_id'] = unquote(component_id.strip())
        if client_id is not None:
            geni_props['client_id'] = client_id.strip()
        if component_name is not None:
            geni_props['component_name'] = component_name.strip()        
        if sliver_id is not None:
            geni_props['sliver_id'] = sliver_id.strip()
        if component_manager_id is not None:
            geni_props['component_manager_id'] = component_manager_id.strip()
        if exclusive is not None:
            geni_props['exclusive'] = self._parse_xml_bool(exclusive)
        if colocate is not None:
            geni_props['colocate'] = colocate.strip()

        slice_uuid = kwargs.get("slice_uuid")
        if slice_uuid is not None:
            geni_props['slice_uuid'] = slice_uuid
    
        # Set URN, ID, and name
        rspec_type = kwargs.get("rspec_type", None)
        if rspec_type == RSpec3Decoder.RSpecADV:
            node["urn"] = RSpec3Decoder.rspec_create_urn(geni_props['component_id'])
            node["id"] = self.geni_urn_to_id(geni_props['component_id'])
            self._component_id_cache[component_id.strip()] = doc
            if component_name:
                node["name"] = geni_props['component_name']
        elif rspec_type == RSpec3Decoder.RSpecManifest:
            slice_urn = kwargs.get("slice_urn")
            geni_props['slice_urn'] = slice_urn
            node["urn"] = RSpec3Decoder.rspec_create_urn(slice_urn+"+node+"+geni_props['client_id'])
            node["id"] = self.geni_urn_to_id(slice_urn+"_node_"+geni_props['client_id'])
            node["name"] = geni_props['client_id']
            if component_id is not None:
                if 'relations' not in node:
                    node['relations'] = {}
                if 'over' not in node['relations']:
                    node['relations']['over'] = []
                node['relations']['over'].append({"href": component_id, "rel": "full"})
        
        kwargs.pop("parent", None)
        self._encode_children(doc, node, collection=collection,
            parent=node, **kwargs)
        
        collection["nodes"].append(node)
        if node.get("urn", None) is not None:
            pointer = self._jsonpointer_path + "/nodes/%d" % (len(collection["nodes"]) - 1)
            self._urn_cache[node["urn"]] = pointer 
            
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        return node
        
    def _encode_rspec_interface(self, doc, out, collection, **kwargs):
        assert isinstance(out, dict)
        port = {}
        port["$schema"] = UNISDecoder.SCHEMAS["port"]
        
        # Parse GENI specific properties
        if "properties" not in port:
            port["properties"] = {}
        if self.geni_ns not in port["properties"]:
            port["properties"][self.geni_ns] = {}
        
        geni_props = port["properties"][self.geni_ns]
        attrib = dict(doc.attrib)
        # From common.rnc
        # From request.rnc & ad.rnc
        component_id = attrib.pop('component_id', None)
        component_name = attrib.pop('component_name', None)
        role = attrib.pop('role', None)
        public_ipv4 = attrib.pop('public_ipv4', None)
        # From request.rnc
        client_id = attrib.pop('client_id', None)
        # From manifest
        sliver_id = attrib.pop('sliver_id', None)
        mac_address = attrib.pop('mac_address', None)
        
        if component_id is not None:
            geni_props['component_id'] = unquote(component_id.strip())
        if client_id is not None:
            geni_props['client_id'] = client_id.strip()
        if component_name is not None:
            geni_props['component_name'] = component_name.strip()
        if sliver_id is not None:
            geni_props['sliver_id'] = sliver_id.strip()
        if role is not None:
            geni_props['role'] = role.strip()
        if public_ipv4 is not None:
            geni_props['public_ipv4'] = public_ipv4.strip()
            port["address"] = {
                "type": "ipv4",
                "address": geni_props['public_ipv4']
            }
        if mac_address is not None:
            geni_props['mac_address'] = mac_address.strip()
            port["address"] = {
                "type": "mac",
                "address": geni_props['mac_address']
            }

        slice_uuid = kwargs.get("slice_uuid")
        if slice_uuid is not None:
            geni_props['slice_uuid'] = slice_uuid
        
        # Set URN, ID, and name
        rspec_type = kwargs.get("rspec_type", None)
        if rspec_type == RSpec3Decoder.RSpecADV:
            port["urn"] = RSpec3Decoder.rspec_create_urn(geni_props['component_id'])
            port["id"] = self.geni_urn_to_id(geni_props['component_id'])
            self._component_id_cache[component_id.strip()] = doc
            if component_name:
                port["name"] = geni_props['component_name']
        elif rspec_type == RSpec3Decoder.RSpecManifest:
            slice_urn = kwargs.get("slice_urn")
            geni_props['slice_urn'] = slice_urn
            port["urn"] = RSpec3Decoder.rspec_create_urn(slice_urn+"+interface+"+geni_props['client_id'])
            port["id"] = self.geni_urn_to_id(slice_urn+"_interface_"+geni_props['client_id'])
            port["name"] = geni_props['client_id']
            if component_id is not None:
                if 'relations' not in port:
                    port['relations'] = {}
                if 'over' not in port['relations']:
                    port['relations']['over'] = []
                port['relations']['over'].append({"href": component_id, "rel": "full"})
            
        kwargs.pop("parent", None)
        self._encode_children(doc, port, collection=collection,
            parent=port, **kwargs)
        
        if out == self._parent_collection:
            if "ports" not in out:
                out["ports"] = []
            out["ports"].append(port)
            pointer = self._jsonpointer_path + \
                "/ports/%d" % (len(out["ports"]) - 1)
        else:
            if "ports" not in collection:
                collection["ports"] = []
            collection["ports"].append(port)
            if "ports" not in out:
                out["ports"] = []
            pointer = self._jsonpointer_path + \
                "/ports/%d" % (len(collection["ports"]) - 1)
            out["ports"].append({"href": pointer, "rel": "full"})
        
        if port.get("urn", None) is not None:
            self._urn_cache[port["urn"]] = pointer 
        
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        return port
    
    def _encode_rspec_link(self, doc, out, collection, **kwargs):
        assert isinstance(out, dict)
        link = {}
        link["$schema"] = UNISDecoder.SCHEMAS["link"]
        
        # Parse GENI specific properties
        if "properties" not in link:
            link["properties"] = {}
        if self.geni_ns not in link["properties"]:
            link["properties"][self.geni_ns] = {}
        
        geni_props = link["properties"][self.geni_ns]
        attrib = dict(doc.attrib)
        
        # From ad.rnc
        component_id = attrib.pop('component_id', None)
        component_name = attrib.pop('component_name', None)
        # From request.rnc
        client_id = attrib.pop('client_id', None)
        # From mainfest.rnc
        vlantag = attrib.pop('vlantag', None)
        sliver_id = attrib.pop('sliver_id', None)
        
        if component_id is not None:
            geni_props['component_id'] = unquote(component_id.strip())
        if component_name is not None:
            geni_props['component_name'] = component_name.strip()
        if client_id is not None:
            geni_props['client_id'] = client_id.strip()
        if vlantag is not None:
            geni_props['vlantag'] = vlantag.strip()
        if sliver_id is not None:
            geni_props['sliver_id'] = sliver_id.strip()

        slice_uuid = kwargs.get("slice_uuid")
        if slice_uuid is not None:
            geni_props['slice_uuid'] = slice_uuid
            
        # Set URN, ID, and name
        rspec_type = kwargs.get("rspec_type", None)
        if rspec_type == RSpec3Decoder.RSpecADV:
            link["urn"] = RSpec3Decoder.rspec_create_urn(geni_props['component_id'])
            link["id"] = self.geni_urn_to_id(geni_props['component_id'])
            self._component_id_cache[component_id.strip()] = doc
            if component_name:
                link["name"] = geni_props['component_name']
        elif rspec_type == RSpec3Decoder.RSpecManifest:
            slice_urn = kwargs.get("slice_urn")
            geni_props['slice_urn'] = slice_urn
            link["urn"] = RSpec3Decoder.rspec_create_urn(slice_urn+"+link+"+geni_props['client_id'])
            link["id"] = self.geni_urn_to_id(slice_urn+"_link_"+geni_props['client_id'])
            link["name"] = geni_props['client_id']
            if component_id is not None:
                if 'relations' not in link:
                    link['relations'] = {}
                if 'over' not in link['relations']:
                    link['relations']['over'] = []
                link['relations']['over'].append({"href": component_id, "rel": "full"})
        
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        kwargs.pop("parent", None)
        self._encode_children(doc, link, collection=collection,
            parent=link, **kwargs)
        
        # First try to establish links by interface_ref
        interface_refs = geni_props.get("interface_refs", [])
        if len(interface_refs) == 2:
            hrefs = []
            for interface in interface_refs:
                if rspec_type == RSpec3Decoder.RSpecManifest:
                    interface_id = interface["sliver_id"]
                    if not interface_id:
                        raise UNISDecoderException("Not valid Link" + etree.tostring(doc, pretty_print=True))
                    element = self._find_sliver_id(interface_id, "interface")
                else:
                    interface_id = interface.get("component_id", None)
                    if not interface_id:
                        raise UNISDecoderException("Not valid Link" + etree.tostring(doc, pretty_print=True))
                    element = self._find_component_id(interface_id, "interface")
                    if element is None:
                        return
                hrefs.append(self._make_self_link(element, rspec_type=rspec_type))
            link["directed"] = False
            link["endpoints"] = [
                {
                    "href": hrefs[0],
                    "rel": "full"
                },
                {
                    "href": hrefs[1],
                    "rel": "full"
                }
            ]
        else:
            # Try to find the link's endpoints in the properties
            link_props = geni_props.get('properties', None)
            if link_props is not None:
                # Assume default endpoints at first
                ends_id = [
                    {"source_id": None, "dest_id": None, "props": {}},
                    {"source_id": None, "dest_id": None, "props": {}},
                ]
                # Then make sure that all for all properties there is at most two endpoints
                for prop in link_props:
                    source_id = prop.get("source_id", None) 
                    dest_id = prop.get("dest_id", None) 
                    if ends_id[0]["source_id"] is None and source_id is not None and dest_id is not None:
                        ends_id[0]["source_id"] = source_id
                        ends_id[0]["dest_id"] = dest_id
                        ends_id[0]["props"].update(prop)
                    elif ends_id[1]["source_id"] is None and source_id is not None and dest_id is not None:
                        ends_id[1]["source_id"] = source_id
                        ends_id[1]["dest_id"] = dest_id
                        ends_id[1]["props"].update(prop)
                    elif source_id is None or dest_id is None:
                        raise UNISDecoderException("Incomplete link property")
                    else:
                        if {"source_id": source_id, "dest_id": dest_id} not in ends_id:
                            raise UNISDecoderException("end matching source and dest")
                # Check if the link is unidirectional or bidirectional
                unidirectional = {"source_id": None, "dest_id": None} in ends_id
                
                if unidirectional is True:
                    ends_id.remove({"source_id": None, "dest_id": None})
                    link["directed"] = True
                    src_port = self._find_component_id(ends_id[0]["source_id"], "interface")
                    dst_port = self._find_component_id(ends_id[0]["dest_id"], "interface")
                    
                    if src_port is None:
                        src_port = ends_id[0]["source_id"]
                    else:
                        src_port = self._make_self_link(src_port)
                        
                    if dst_port is None:
                        dst_port = ends_id[0]["dest_id"]
                    else:
                        dst_port = self._make_self_link(dst_port)
                    
                    
                    link["endpoints"] = {
                        "source": {
                            "href": self._make_self_link(src_port),
                            "rel": "full"
                        },
                        "sink": {
                            "href": self._make_self_link(dst_port),
                            "rel": "full"
                        }
                    }
                    if "capacity" in ends_id[0]["props"]:
                        link["capacity"] = float(ends_id[0]["props"]["capacity"])
                else:
                    link["directed"] = False
                    src_port = self._find_component_id(ends_id[0]["source_id"], "interface")
                    dst_port = self._find_component_id(ends_id[0]["dest_id"], "interface")
                    if src_port is None:
                        src_port = ends_id[0]["source_id"]
                    else:
                        src_port = self._make_self_link(src_port)
                        
                    if dst_port is None:
                        dst_port = ends_id[0]["dest_id"]
                    else:
                        dst_port = self._make_self_link(dst_port)
                    
                    link["endpoints"] = [
                        {
                            "href": src_port,
                            "rel": "full"
                        },
                        {
                            "href": dst_port,
                            "rel": "full"
                        }
                    ]
                    # Check if the links has symmetric capacity
                    if ends_id[0]["props"].get("capacity", None) == \
                        ends_id[1]["props"].get("capacity", None) and \
                        ends_id[1]["props"].get("capacity", None) is not None:
                        link["capacity"] = float(ends_id[0]["props"]["capacity"])
        
        if link.get("endpoints", None) is None:
            print json.dumps(link, indent=2)
            raise UNISDecoderException(
                "Cannot accept link with no endpoints in %s " % \
                etree.tostring(doc, pretty_print=True)
            )
        
        if out == self._parent_collection:
            if "links" not in out:
                out["links"] = []
            out["links"].append(link)
            pointer = self._jsonpointer_path + \
                "/links/%d" % (len(out["links"]) - 1)
        else:
            if "links" not in collection:
                collection["links"] = []
            collection["links"].append(link)
            if "links" not in out:
                out["links"] = []
            pointer = self._jsonpointer_path + \
                "/links/%d" % (len(collection["links"]) - 1)
            out["links"].append({"href": pointer, "rel": "full"})
        
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        return link
    
    def _encode_rspec_available(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        if "available" not in geni_props:
            geni_props["available"] = {}
        available = geni_props["available"]
        attrib = dict(doc.attrib)
        # From ad.rnc
        now = attrib.pop('now', None)
        
        if now is not None:
            available["now"] = self._parse_xml_bool(now)
            if available["now"]:
                parent["status"] = "AVAILABLE"
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, available, collection=collection,
            parent=parent, **kwargs)
        return {"available": available}
    
    def _make_self_link(self, element, rspec_type=None):
        if element is None:
            raise UNISDecoderException("Cannot make self link to NONE")
        if rspec_type == RSpec3Decoder.RSpecManifest:
            urn = element.get("sliver_id", None)
        else:
            urn = element.get("component_id", None)
            
        if not urn:
            raise UNISDecoderException("Cannot link to an element withour URN")
        
        # First try cache
        urn = unquote(urn.strip())
        if urn in self._urn_cache:
            return self._urn_cache[urn]
       
        #if rspec_type == RSpec3Decoder.RSpecManifest:
        #    jpath = "[?(@.properties.geni.sliver_id==\"%s\")]" % urn
        #else:
        #    jpath = "[?(@.urn==\"%s\")]" % urn
                
        #self._urn_cache[urn] = jpath
        #self._subsitution_cache[urn] = jpath
        #return
        
        # Try to construct xpath to make the lookup easier
        xpath = self._tree.getpath(element)
        
        peices = xpath.split("/")[2:]
        names_map = {
            "topology": "topolgies",
            "domain": "domains",
            "rspec": "domains",
            "network": "networks",
            "node": "nodes",
            "port": "ports",
            "interface": "ports",
            "link": "links",
            "path": "paths",
            "service": "services",
            "metadata": "metadata",
        }
        jpath = []
        add_urn = False
        collections = ["topolgies", "domains"]
        for p in peices:
            p = p[p.find(":") + 1:]
            if "[" in p:
                name, index = p.split("[")
                index = "[" + str(int(index.rstrip("]")) - 1) + "]"
            else:
                name = p
                index = ""
            if name not in names_map:
                raise UNISDecoderException("Unrecongized type '%s' in '%s'" % (name, xpath))
            if name not in collections:
                add_urn = True
                if len(jpath) > 0:
                    lastname = jpath[-1].split("[")[0]
                    if lastname not in collections:
                        jpath = jpath[:-1]
            if names_map[name] in collections and index == "":
                index = "[0]"
            jpath.append(names_map[name] + index)
        jpath =  "$." + ".".join(jpath)
        if add_urn:
            if jpath.endswith("]"):
                jpath = jpath[:jpath.rindex("[")]
            if rspec_type == RSpec3Decoder.RSpecManifest:
                jpath += "[?(@.properties.geni.sliver_id==\"%s\")]" % urn
            else:
                jpath += "[?(@.urn==\"%s\")]" % urn
        self._urn_cache[urn] = jpath
        self._subsitution_cache[urn] = jpath
        return jpath
    
    def _find_sliver_id(self, urn, component_type, try_hard=False):
        """
        Looks for the any element with sliver_id == urn and of type
        component_type. component_type examples: interface and node.
        This method trys all special cases I've seen and issues a
        warning log if the URN found but was not in the right format.
        """
        def escape_urn(u):
            return u.replace("/", "%2F").replace("#", "%23")
        
        if urn in self._sliver_id_cache:
            return self._sliver_id_cache[urn]
        if self._root is None:
            return None
        xpath = ".//rspec:%s[@sliver_id='%s']" % (component_type, urn)
        if try_hard == True:
            escaped_urn = escape_urn(urn)
            xpath = ".//rspec:%s[@sliver_id='%s' or @sliver_id='%s']" \
                % (component_type, urn, escaped_urn)
        result = self._root.xpath(xpath, namespaces={"rspec": RSpec3Decoder.rspec3})
        
        if len(result) > 1:
            raise UNISDecoderException("Found more than one node with the URN '%s'" % urn)
        elif len(result) == 1:
            result = result[0]
        else:
            result = None
        self._sliver_id_cache[urn] = result
        return result
    
    def _find_component_id(self, urn, component_type, try_hard=False):
        """
        Looks for the any element with component_id == urn and of type
        component_type. component_type examples: interface and node.
        This method trys all special cases I've seen and issues a
        warning log if the URN found but was not in the right format.
        """
        def escape_urn(u):
            return u.replace("/", "%2F").replace("#", "%23")
        
        if urn in self._component_id_cache:
            return self._component_id_cache[urn]
        if self._root is None:
            return None
        xpath = ".//rspec:%s[@component_id='%s']" % (component_type, urn)
        if try_hard == True:
            escaped_urn = escape_urn(urn)
            xpath = ".//rspec:%s[@component_id='%s' or @component_id='%s']" \
                % (component_type, urn, escaped_urn)
        result = self._root.xpath(xpath, namespaces={"rspec": RSpec3Decoder.rspec3})
        
        if len(result) > 1:
            raise UNISDecoderException("Found more than one node with the URN '%s'" % urn)
        elif len(result) == 1:
            result = result[0]
        else:
            result = None
        self._component_id_cache[urn] = result
        return result
    
    def _encode_rspec_sliver_type(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if 'sliver_type' not in geni_props:
            geni_props['sliver_type'] = {}
        sliver_type = geni_props['sliver_type']
        
        attrib = dict(doc.attrib)
        # From common.rnc
        name = attrib.pop('name', None)
        # From ad.rnc
        default = attrib.pop('default', None)
        
        if name is not None:
            sliver_type["name"] = name.strip()
        if default is not None:
            sliver_type["default"] = default.strip()
        
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, sliver_type, collection=collection,
            parent=parent, **kwargs)
        return {"sliver_type": sliver_type}
    
    def _encode_rspec_location(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        
        if "location" not in parent:
            parent["location"] = {}
        location = parent["location"]
       
        xml_attribs = dict(doc.attrib)
        schema_attribs = [
            # From common.rnc
            "country", "longitude", "latitude"
        ]
        location.update(dict(
                [
                    (name, xml_attribs.pop(name).strip()) \
                    for name in xml_attribs.keys() \
                    if name in schema_attribs
                ]
            )
        )
        # Convert values
        if location['longitude'] is not None:
            location['longitude'] = float(location['longitude'])
        if location['latitude'] is not None:
            location['latitude'] = float(location['latitude'])
        
        if len(xml_attribs) != 0:
            sys.stderr.write("Unparsed attributes: %s\n" % xml_attribs)
        
        self._encode_children(doc, location, collection=collection,
            parent=parent, **kwargs)
        return {"location": location}
    
    def _encode_rspec_hardware_type(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "hardware_types" not in geni_props:
            geni_props["hardware_types"] = []
        hardware_types = geni_props["hardware_types"]
        hardware_type = {}
        
        attrib = dict(doc.attrib)
        # From common.rnc
        name = attrib.pop('name')
        if name:
            hardware_type['name'] = name.strip()
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, hardware_type, collection=collection, parent=parent, **kwargs)
        hardware_types.append(hardware_type)
        return {"hardware_types": hardware_types}
    
    def _encode_rspec_disk_image(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        
        if "disk_images" not in out:
            out["disk_images"] = []
        disk_images = out["disk_images"]
        disk_image = {}        
        
        xml_attribs = dict(doc.attrib)
        schema_attribs = [
            # From common.rnc
            "name", "os", "version", "description",
            # From ad.rnc
            "default",
        ]
        disk_image = dict(
            [
                (name, xml_attribs.pop(name).strip()) \
                for name in xml_attribs.keys() \
                if name in schema_attribs
            ]
        )
        if len(xml_attribs) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % xml_attribs)
        
        self._encode_children(doc, disk_image, collection=collection,
            parent=parent, **kwargs)
        disk_images.append(disk_image)
        return {"disk_images": disk_images}
    
    def _encode_rspec_relation(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if 'relations' not in geni_props:
            geni_props['relations'] = []
        relations = geni_props['relations']
        relation = {}
        
        attrib = dict(doc.attrib)
        # From common.rnc
        rtype = attrib.pop('type')
        # From ad.rnc
        component_id = attrib.pop('component_id', None)
        # From request.rnc
        client_id = attrib.pop('client_id', None)
        
        relation["type"] = rtype.strip()
        if component_id is not None:
            relation["component_id"] = component_id.strip()
            if "relations" not in parent:
                parent["relations"] = {}
            if relation["type"] not in parent["relations"]:
                parent["relations"][relation["type"]] = []
            parent["relations"][relation["type"]].append(
                {"href": '$.nodes[?(@.urn=="%s")]' % component_id, "rel": "full"}
            )
        if client_id is not None:
            relation["client_id"] = client_id.strip()
        
        if len(attrib) > 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, relation, collection=collection,
            parent=parent, **kwargs)
        relations.append(relation)
        return {"relations": relations}
    
    
    def _encode_rspec_link_type(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["link"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "link_types" not in geni_props:
            geni_props["link_types"] = []
        link_types = geni_props["link_types"]
        link_type = {}
        
        attrib = dict(doc.attrib)
        # From common.rnc
        name = attrib.pop('name')
        klass = attrib.pop('class', None)
        
        if name:
            link_type['name'] = name.strip()
        if klass:
            link_type['class'] = klass.strip()
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, link_type, collection=collection, parent=parent, **kwargs)
        link_types.append(link_type)
        return {"link_types": link_types}
    
    def _encode_rspec_component_manager(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["link"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "component_managers" not in geni_props:
            geni_props["component_managers"] = []
        component_managers = geni_props["component_managers"]
        component_manager = {}
        
        attrib = dict(doc.attrib)
        # From ad.rnc
        name = attrib.pop('name')
        
        if name:
            component_manager['name'] = name.strip()
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, component_manager, collection=collection, parent=parent, **kwargs)
        component_managers.append(component_manager)
        return {"component_managers": component_managers}
    
    def _encode_rspec_interface_ref(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["link"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "interface_refs" not in geni_props:
            geni_props["interface_refs"] = []
        interface_refs = geni_props["interface_refs"]
        interface_ref = {}
        
        attrib = dict(doc.attrib)
        
        # From ad.rnc and manifest.rnc
        component_id = attrib.pop('component_id', None)
        # From request.rnc
        client_id = attrib.pop('client_id', None)
        # From manifest.rnc
        sliver_id = attrib.pop('sliver_id', None)
        
        if component_id:
            interface_ref['component_id'] = unquote(component_id.strip())
        if client_id:
            interface_ref['client_id'] = client_id.strip()
        if sliver_id:
            interface_ref['sliver_id'] = sliver_id.strip()
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, interface_ref, collection=collection, parent=parent, **kwargs)
        interface_refs.append(interface_ref)
        return {"interface_refs": interface_refs}

    def _encode_rspec_property(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["link"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "properties" not in geni_props:
            geni_props["properties"] = []
        properties = geni_props["properties"]
        prop = {}
        
        attrib = dict(doc.attrib)
        # From common.rnc
        source_id = attrib.pop('source_id', None)
        dest_id = attrib.pop('dest_id', None)
        capacity = attrib.pop('capacity', None)
        latency = attrib.pop('latency', None)
        packet_loss = attrib.pop('packet_loss', None)
        
        if source_id:
            prop['source_id'] = source_id.strip()
        if dest_id:
            prop['dest_id'] = dest_id.strip()
        if capacity:
            prop['capacity'] = capacity.strip()
        if latency:
            prop['latency'] = latency.strip()
        if packet_loss:
            prop['packet_loss'] = packet_loss.strip()
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, prop, collection=collection, parent=parent, **kwargs)
        properties.append(prop)
        return {"properties": prop}
        
    def _encode_rspec_host(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) in [UNISDecoder.SCHEMAS["node"], UNISDecoder.SCHEMAS["port"]], \
            "Found parent '%s'." % (parent.get("$schema", None))
        
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "hosts" not in geni_props:
            geni_props["hosts"] = []
        hosts = geni_props["hosts"]
        host = {}        
        
        attrib = dict(doc.attrib)
        # From manifest.rnc
        hostname = attrib.pop('name', None)
        
        if hostname:
            host['hostname'] = hostname.strip()
            parent["id"] = hostname
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, host, collection=collection, parent=parent, **kwargs)
        hosts.append(host)
        return {'hosts': hosts}
    
    def _encode_rspec_ip(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["port"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "ip" not in geni_props:
            geni_props["ip"] = {}
        ip = geni_props["ip"]
        
        attrib = dict(doc.attrib)
        # From common.rnc
        address = attrib.pop('address')
        netmask = attrib.pop('netmask', None)
        ip_type = attrib.pop('type', None)
        
        if address:
            ip['address'] = address.strip()
        if netmask:
            ip['netmask'] = netmask.strip()
        if ip_type:
            ip['type'] = ip_type.strip().lower()
        else:
            ip['type'] = "ipv4"
        
        parent["address"] = {
            "address": ip['address'],
            "type": ip['type'],
        }
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, ip, collection=collection, parent=parent, **kwargs)
        return {'ip': ip}
    
    def _encode_gemini_node(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "gemini" not in geni_props:
            geni_props["gemini"] = {}
        gemini_props = geni_props["gemini"]
        
        attrib = dict(doc.attrib)
        # From common.rnc
        node_type = attrib.pop('type')
        
        if node_type:
            gemini_props['type'] = node_type.strip()
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, gemini_props, collection=collection, parent=parent, **kwargs)
        return {'gemini': gemini_props}
        
    def _encode_gemini_monitor_urn(self, doc, out, collection, parent, **kwargs):
        assert isinstance(out, dict)
        assert isinstance(parent, dict)
        assert parent.get("$schema", None) == UNISDecoder.SCHEMAS["node"], \
            "Found parent '%s'." % (parent.get("$schema", None))
        # Parse GENI specific properties
        if "properties" not in parent:
            parent["properties"] = {}
        if self.geni_ns not in parent["properties"]:
            parent["properties"][self.geni_ns] = {}
        geni_props = parent["properties"][self.geni_ns]
        
        if "gemini" not in geni_props:
            geni_props["gemini"] = {}
        gemini_props = geni_props["gemini"]
        
        attrib = dict(doc.attrib)
        # From common.rnc
        name = attrib.pop('name')
        
        if name:
            gemini_props['monitor_urn'] = name.strip()
        
        if len(attrib) != 0:
            pass
            #sys.stderr.write("Unparsed attributes: %s\n" % attrib)
        
        self._encode_children(doc, gemini_props, collection=collection, parent=parent, **kwargs)
        return {'gemini': gemini_props}


def main():
    parser = argparse.ArgumentParser(
        description="Encodes RSpec V3 and the different perfSONAR's topologies to UNIS"
    )
    parser.add_argument('-t', '--type', required=True, type=str,
        choices=["rspec3", "ps"], help='Input type (rspec3 or ps)')
    parser.add_argument('-o', '--output', type=str, default=None,
        help='Output file')
    parser.add_argument('-l', '--log', type=str, default="unisencoder.log",
        help='Log file.')
    parser.add_argument('--slice_urn', type=str, default=None,
        help='Slice URN.')
    parser.add_argument('--slice_cred', type=str, default=None,
        help='Slice credential file (XML)')
    parser.add_argument('-m', '--component_manager_id', type=str, default=None,
        help='The URN of the component manager of the advertisment RSpec.')
    parser.add_argument('--indent', type=int, default=2,
        help='JSON output indent.')
    parser.add_argument('filename', type=str, help='Input file.')    
    args = parser.parse_args()
    
    setup_logger(args.log)
    
    if args.filename is None:
        in_file = sys.stdin
    else:
        in_file = open(args.filename, 'r')

    try:
        if args.slice_cred and args.slice_urn:
            raise Usage("Must specify only one of '--slice_urn' or '--slice_cred'")
        elif args.slice_cred:
            from sfa.trust.credential import Credential as GENICredential
            import hashlib
            try:
                cred = GENICredential(filename=args.slice_cred)
                slice_urn = cred.get_gid_object().get_urn()
                slice_uuid = cred.get_gid_object().get_uuid()
                if not slice_uuid:
                    slice_uuid = hashlib.md5(cred.get_gid_object().get_urn()).hexdigest()
                    slice_uuid = str(uuid.UUID(slice_uuid))
                else:
                    slice_uuid = str(uuid.UUID(int=slice_uuid))
            except Exception, msg:
                raise Usage(msg)
        else:
            slice_urn = args.slice_urn
            slice_uuid = None
    except Usage, err:
        print >>sys.stderr, err.msg
        return

    topology = etree.parse(in_file)
    in_file.close()
    
    if args.type == "rspec3":
        encoder = RSpec3Decoder()
        kwargs = dict(slice_urn=slice_urn,
                      slice_uuid=slice_uuid,
                      component_manager_id=args.component_manager_id)
    elif args.type == "ps":
        encoder = PSDecoder()
        kwargs = dict()
    
    topology_out = encoder.encode(topology, **kwargs)

    if args.output is None:
        out_file = sys.stdout
    else:
        out_file = open(args.output, 'w')
    
    json.dump(topology_out, fp=out_file, indent=args.indent)
    out_file.close()
    
if __name__ == '__main__':
    main()
