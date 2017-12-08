$("input[type=checkbox]").on('change', function () {
   var self = $(this);
   $.post("/results", {change: self.attr("name"), person: self.attr("id"), title: self.attr("value")});
});


