var UNIS_URL = "http://localhost:8888";
var MS_URL = "http://localhost:8888";
var MD_QUERY = "/metadata?subject.href=http://localhost:8888/nodes/519b8fd6164ed872c827ea4d";
var INITIAL_DATA_QUERY = "";
var UPDATE_INTERVAL = 2000; //query every update_interval in ms
mdids = {};
function fill_mdids(data){
    for(var i = 0; i<data.length; i++){
	mdids[data[i]["id"]] = {
	    data_pairs: [],
	    options: {
		title: {
		    text: data[i]["eventType"],
		    show: true
		},
		axes: {xaxis: {
		    renderer: $.jqplot.DateAxisRenderer,
		    tickOptions: {formatString: '%T'}
		}}
	    }
	};

    }
}

function parse_data(data) {
    var ret = []
    for(var i = data.length-1; i >= 0; i--){
	ret.push([data[i].ts/1000,
		  parseFloat(data[i].value)]);
    }
    return ret;
}

function plot_id(idd) {
    if (mdids[idd]["data_pairs"] == []){
	console.log("empty");
	return
    }
    $('body').append("<div id=\""+idd+"\" style=\"height:400px;width:1600px; \"></div>");
    mdids[idd]["plot"] = $.jqplot(idd,
				  [mdids[idd]["data_pairs"]],
				  mdids[idd]["options"]);
    console.log("finished plot " + idd);
}

function get_and_plot(idd) {
    var dfd = $.Deferred();
    $.get(MS_URL + "/data/" + idd + INITIAL_DATA_QUERY, {},
	  function (data) {
	      mdids[idd]["data_pairs"] = parse_data(data);
	      plot_id(idd);
	      dfd.resolve();
	  });
    return dfd.promise();
}

function get_initial_data(){
    console.log("get_initial_data");
    var dfd = $.Deferred();
    var promise;
    for( var idd in mdids ){
	console.log("calling get_and_plot");
	promise = get_and_plot(idd);
    }
    $.when(promise).then(dfd.resolve);
    return dfd.promise();
}


var initial = $.get(UNIS_URL + MD_QUERY, {}, fill_mdids).then(get_initial_data);

$.when(initial).then(start_updates);
console.log("done");

function start_updates(){
    window.setInterval(
	function () {
	    console.log("doing update");
	    for( var idd in mdids ){
		var plot = mdids[idd]["plot"]
		var plot_data = plot.series[0].data;
		var dlen = plot_data.length;
		var latest_ts = plot_data[dlen-1][0]*1000;
		$.get(
		    MS_URL + "/data/" + idd + "?ts=gt=" + latest_ts,
		    {},
		    (function (data) {
			idd = this.idd;
			dlist = parse_data(data);
			if(dlist.length>0){
			    mdids[idd]["plot"].series[0].data = mdids[idd]["plot"].series[0].data.concat(dlist);
			    mdids[idd]["plot"].replot({resetAxes: true});
			}
		    }).bind({"idd": idd}));
	    }
	},
	UPDATE_INTERVAL);
}

$.when(initial).then(start_updates);
console.log("done");

function start_updates(){
    window.setInterval(
	function () {
	    console.log("doing update");
	    for( var idd in mdids ){
		var plot = mdids[idd]["plot"]
		var plot_data = plot.series[0].data;
		var dlen = plot_data.length;
		var latest_ts = plot_data[dlen-1][0]*1000;
		$.get(
		    MS_URL + "/data/" + idd + "?ts=gt=" + latest_ts,
		    {},
		    (function (data) {
			idd = this.idd;
			dlist = parse_data(data);
			if(dlist.length>0){
			    mdids[idd]["plot"].series[0].data = mdids[idd]["plot"].series[0].data.concat(dlist);
			    mdids[idd]["plot"].replot({resetAxes: true});
			}
		    }).bind({"idd": idd}));
	    }
	},
	UPDATE_INTERVAL);
}
