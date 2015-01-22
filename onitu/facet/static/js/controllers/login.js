/*
 * login.js for onitu
 * by lenorm_f
 */

"use strict";

facetControllers.controller("loginFormCtrl", [ "$scope", "Restangular",
    function ($scope, Restangular) {
      $scope.login = {};
      $scope.login.submit = function (item, event) {

      var loginurl = Restangular.all('login');
      loginurl.post({user: $scope.login.name,
		     password: $scope.login.password})

      };

    }
]);
