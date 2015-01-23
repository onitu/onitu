/*
 * navbarhome.js for onitu
 * by lenorm_f
 */

"use strict";

facetControllers.controller("navbarHomeCtrl", [ "$rootScope", "$scope", "$location",
    function ($rootScope, $scope, $location) {
        // This function is used by the home sidebar
        $rootScope.isPathActive = function (viewLocation) { 
            return viewLocation === $location.path();
        }
    }
])
