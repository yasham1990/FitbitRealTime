function getDate(dateStr) {
    var split = dateStr.split('-'),
        year = split[0],
        month = parseInt(split[1], 10) - 1,
        day = parseInt(split[2]);
    return Date.UTC(year, month, day);
}