/*
 * breadcrumb.js for onitu
 * by lenorm_f
 */

"use strict";

facetControllers.controller("breadcrumbHomeCtrl", [ "$scope", "$location",
    function ($scope, $location) {
        var capitalize_dirs = function (path) {
            var dirs = path.split("/");

            for (var i = 0; i < dirs.length; i++) {
                // Capitalize
                dirs[i] = dirs[i].charAt(0).toUpperCase() + dirs[i].slice(1);;
            }

            return dirs;
        }

        $scope.$on("$locationChangeSuccess", function (e) {
            $scope.path = capitalize_dirs($location.path().substr(1));
        });
    }
]);
