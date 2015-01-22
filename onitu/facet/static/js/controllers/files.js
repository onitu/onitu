/*
 * files.js for onitu
 * by lenorm_f
 */

"use strict";

facetControllers.controller("filesListCtrl", [ "$rootScope", "$scope", "$routeParams", "$location", "filesFactory",
	function ($rootScope, $scope, $routeParams, $location, filesFactory) {
        var assign_files_by_dir = function (files) {
            var f = {
                orphans: [],
                by_dir: {},
            }

            $.each(files, function (_, file) {
                var slash_idx = file.filename.indexOf("/");

                if (slash_idx > -1) {
                    var dir = file.filename.substr(0, slash_idx);
                    var path_remaining = file.filename.substr(slash_idx + 1);

                    file.filename = path_remaining;

                    if (dir in f.by_dir) {
                        f.by_dir[dir].push(file);
                    } else {
                        f.by_dir[dir] = [file];
                    }
                } else {
                    f.orphans.push(file);
                }
            });

            return f;
        }

        $scope.fileTypeToAwesomeClass = function (filetype) {
            var awesome_class_ref = {
                "file": "fa-file-o",
                "archive": "fa-file-archive-o",
                "audio": "fa-file-audio-o",
                "code": "fa-file-code-o",
                "excel": "fa-file-excel-o",
                "image": "fa-file-image-o",
                "pdf": "fa-file-pdf-o",
                "powerpoint": "fa-file-powerpoint-o",
                "text": "fa-file-text-o",
                "video": "fa-file-video-o",
                "word": "fa-file-word-o",
                "directory": "fa-folder",
            }

            filetype = filetype.toLowerCase();
            if (filetype in awesome_class_ref) {
                return awesome_class_ref[filetype];
            } else {
                return awesome_class_ref["file"];
            }
        }

        $scope.displayFile = function (file) {
            $location.path("/files/" + file.uptodate[0] + "/" + file.filename + "/info");
        }

        filesFactory.getFiles($routeParams.type).then(function (files) {
            files = assign_files_by_dir(files);

            $.each(files.by_dir, function (dirname, service) {
                $.each(service, function (_, file) {
                    var slash_idx = file.filename.lastIndexOf("/");

                    if (slash_idx > -1) {
                        file.filename = file.filename.substr(slash_idx + 1);
                    }
                });
            });

            // Split the files between orphans (no parent directory) and the rest
            $rootScope.files = files;
        });
	}
]);

facetControllers.controller("fileDetailsCtrl", [ "$rootScope", "$scope", "$routeParams", "filesFactory",
    function ($rootScope, $scope, $routeParams, filesFactory) {
        var drivername = $routeParams.drivername;
        var filename = $routeParams.filename;

        var find_file = function (drivername, filename) {
            // FIXME: works only with orphans
            $.each($rootScope.files.orphans, function (_, file) {
                if (file.filename === filename && file.uptodate.indexOf(drivername) > -1) {
                    $scope.file = file;


                    $.each($rootScope.drivers, function (_, driver) {
                        if (driver.name === drivername) {
                            $scope.driver = driver;

                            return false;
                        }
                    });

                    // FIXME: better preview
                    $scope.trustedFilePath = "";//$scope.driver.options.root + '/' + $scope.file.filename;

                    return false;
                }
            });
        }

        // If the files were not fetched beforehand, update the global cache
        // FIXME: assign_files_by_dir()
        if ($rootScope.files === undefined) {
            filesFactory.getFiles().then(function (files) {
                $rootScope.files = files;
                find_file(drivername, filename);
            });
        } else {
            find_file(drivername, filename);
        }
    }
]);
