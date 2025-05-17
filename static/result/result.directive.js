resultApp.directive("resultPanel", function() {
    return {
    	scope: {
    		"results": "&",
			"queryMode": "<",
    	},
        templateUrl: "/static/result/result.html",
        link: function(scope, element, attrs) {
        	scope.toString = function(array) {
            	var len = array.length;
        		var formatted = [array.length];
        		
        		for(var i = 0; i < len; i++) {
        			formatted[i] = array[i]['codon'] + " (" + array[i]['probability'].toFixed(2) + ")";
        		}
        		
        		return formatted.join(", ");
            };
            
            scope.toCodonString = function(array) {
            	return "[" + array.join("|") + "]";
            };

			scope.codonSequence = function() {
				results = scope.results();
				if (results == null || results.length == 0) {
					return '';
				}
				seq = scope.results().map((x) => x['ambiguous_codon']).join('');
				return seq;
			}
        }
    };
});