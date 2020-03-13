var app = angular.module('app', ['ui.bootstrap']);

app.filter('bytes', function() {
  return function(bytes, precision) {
    if (bytes==0 || isNaN(parseFloat(bytes)) || !isFinite(bytes)) return '-';
    if (typeof precision === 'undefined') precision = 1;
    var units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
      number = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, Math.floor(number))).toFixed(precision) +  ' ' + units[number];
  }
});

app.filter('thousandSuffix', function () {
  return function (input, decimals) {
    var exp, rounded,
      suffixes = ['k', 'M', 'B', 'T', 'P', 'E'];

    if(window.isNaN(input)) {
      return null;
    }

    if(input < 1000) {
      return input;
    }

    exp = Math.floor(Math.log(input) / Math.log(1000));

    return (input / Math.pow(1000, exp)).toFixed(decimals) + suffixes[exp - 1];
  };
});


app.filter('join', function () {
    return function join(array, separator, prop) {
        if (!Array.isArray(array)) {
            return array; // if not array return original - can also throw error
        }

        return (!!prop ? array.map(function (item) {
            return item[prop];
        }) : array).join(separator);
    };
});


app.controller('MainCtrl', function($scope, $http) {

  $scope.Query = function() {
    $http({
      method: 'GET',
      url: '/indices'
    }).then(function (response) {

      $scope.result = response.data;
    });

  };

  $scope.Query();

  // Sorting
  $scope.sortType = 'name';
  $scope.sortReverse = false;
  $scope.searchVal = '';
});

app.controller('TierCtrl', ['$scope', '$rootScope',
  function($scope, $rootScope) {
}]);

