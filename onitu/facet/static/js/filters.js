/*
 * filters.js for onitu
 * by lenorm_f
 */

"user strict";

var facetFilters = angular.module("facetFilters", []);

// koinkoin
facetFilters.filter("fileSize", function () {
	return function (size) {
		bytes = parseInt(size);
		units = ["KB", "MB", "GB", "TB"];
		nb = bytes ? Math.floor(Math.log(bytes) / Math.log(1024)) : bytes;

		if (nb) {
			return (bytes / Math.pow(1024, nb)).toFixed(2) + " " + units[nb - 1];
		} else {
			return bytes + " B";
		}
	};
});
