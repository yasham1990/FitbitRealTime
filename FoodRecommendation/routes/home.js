var Recommender = require('likely');
var mongo = require("./mongo");
var mongoURL = "mongodb://localhost:27017/fitbit";

var Users = ['John'];
var finalCalorie= new Array();
var finalFoodItems= new Array();
var finalUserPreference= new Array();
var tempUserPreference = new Array();
var Cintake = 30;

function recommend(req,res,next) {
    var intakeCalories = req.query.calorie;           //req.calories;
    mongo.connect(mongoURL, function () {
        //console.log('Connected to mongo to get recommendations: ' + mongoURL);
        var coll = mongo.collection('food_data');
        coll.find({},{"_id":0,"__v":0}).toArray(
            function (err, foodData) {

                if (foodData) {
                    //console.log(foodData[0].name);
                    for (var i = 0; i < 1000; i++) {
                        if (foodData[i].calories < intakeCalories) {
                            //console.log("Inside fooddata");
                            var tempArray = [];
                            finalFoodItems.push(foodData[i].name);
                            tempUserPreference.push(foodData[i].rating);
                            tempArray.push(foodData[i].name);
                            tempArray.push(foodData[i].calories);
                            finalCalorie.push(tempArray);
                        }
                    }

                    finalUserPreference.push(tempUserPreference);
                    res.code = "200";
                    res.finalUserPreference=finalUserPreference;
                    res.finalFoodItems = finalFoodItems;
                    res.finalCalorie = finalCalorie;
                    //console.log("***********************************************************");
                    //console.log(finalUserPreference);
                    //console.log(finalFoodItems);
                    //console.log(finalCalorie);
                    //console.log("***********************************************************");
                    finalCalorie=[];
                    finalUserPreference=[];
                    finalFoodItems=[];
                    tempUserPreference=[];
                    return next();
                }
                else {
                    //console.log("unexpected error");
                    res.code = "401";
                }
            });

    });

}
    function mapper(req,res,next)
    {
    var finalUserPreference=res.finalUserPreference;
    var finalFoodItems = res.finalFoodItems;
    var finalCalorie = res.finalCalorie;
        //console.log("*************************************Final Calorie*******************************************************");
        //console.log(finalCalorie);
        //console.log("*************************************User Preference*******************************************************");
        //console.log(finalUserPreference);
        //console.log("*************************************Food Item*******************************************************");
        //console.log(finalFoodItems);
        //console.log("********************************************************************************************");
    var Model = Recommender.buildModel(finalUserPreference, Users, finalFoodItems);

    var allItems = Model.rankAllItems('John');
    var rec = [];
    var elem = [];
    var map = [];

    for (var k = 0; k < allItems.length; k++) {
        for (var j = 0; j < finalCalorie.length; j++) {
            if (allItems[k][0] == finalCalorie[j][0]) {
                map.push({"key": allItems[k][0], "value": Cintake - finalCalorie[j][1]});
            }
        }
    }

    var sorted = map.slice(0).sort(function (a, b) {
        return a.value - b.value;
    });

    var keys = [];
    var value = [];
    for (var i = 0, len = sorted.length; i < len; ++i) {
        keys[i] = sorted[i].key;
        value[i] = sorted[i].value;
    }

    var data = keys.slice(0, 10);
    req.results = data;
        map = [];
    return next();

}

function getCalories(req,res)
{
    var data = req.results;
    var response;
    mongo.connect(mongoURL, function() {
        var coll = mongo.collection('food_data');
        var result_arr=[];
        coll.find({ "name":{ '$in': data}},{ '_id': 0, '__v': 0}).toArray(
            function (err, foodData) {
                if (foodData) {
                    for (var m=0;m<foodData.length;m++)
                    {
                        var temp_arr = [];
                        temp_arr.push(foodData[m].calories);
                        temp_arr.push(foodData[m].name);

                        result_arr.push(temp_arr);
                    }
                    response = JSON.stringify(result_arr.sort().reverse());
                    //console.log("*****************************************************");
                    //console.log(response);

                    res.send(response);
                }
                else{
                    res.code = "401";
                }
            });
    });
}




exports.recommend = recommend;
exports.mapper = mapper;
exports.getCalories = getCalories;
