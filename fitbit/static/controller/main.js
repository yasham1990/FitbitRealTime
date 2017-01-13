
var allergyDetails = {
                "AllergyRecords": [{
                  "allergy_date": "10/20/2000",
                  "allergy_name": "Dust Allergy",
                  "reaction": "Headache",
                  "recordID": "5",
                  "severity": "High fever",
                  "status": "SUCCESS"
                },
                {
                  "allergy_date": "8/21/2000",
                  "allergy_name": "Seasonal Allergy",
                  "reaction": "Heart Pain",
                  "recordID": "5",
                  "severity": "High fever",
                  "status": "SUCCESS"
                }
                ,
                {
                  "allergy_date": "10/20/2000",
                  "allergy_name": "Dust Allergy",
                  "reaction": "Headache",
                  "recordID": "5",
                  "severity": "High fever",
                  "status": "SUCCESS"
                },
                {
                  "allergy_date": "08/10/2005",
                  "allergy_name": "Dust Allergy",
                  "reaction": "leg pain",
                  "recordID": "5",
                  "severity": "High fever",
                  "status": "SUCCESS"
                },
                {
                  "allergy_date": "6/2/2010",
                  "allergy_name": "Seasonal Allergy",
                  "reaction": "stomach ache",
                  "recordID": "5",
                  "severity": "High fever",
                  "status": "SUCCESS"
                },
                {
                  "allergy_date": "10/2/2000",
                  "allergy_name": "Dust Allergy",
                  "reaction": "Headache",
                  "recordID": "5",
                  "severity": "High fever",
                  "status": "SUCCESS"
                },
                {
                  "allergy_date": "1/20/2000",
                  "allergy_name": "Seasonal Allergy",
                  "reaction": "heart attack",
                  "recordID": "5",
                  "severity": "High fever",
                  "status": "SUCCESS"
                }],
                "ForceLogOn": "false",
                "returnCode": "SUCCESS"
              }

 var app = angular.module('app', []);
    app.controller('drag', function($scope , $http) {
      $scope.allergyDetails = allergyDetails.AllergyRecords;
      $scope.sortKey = allergyDetails.AllergyRecords.allergy_name;
 });


         