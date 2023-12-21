(function ($) {
  
    "use strict";
  
      // MENU
      $('.navbar-collapse a').on('click',function(){
        $(".navbar-collapse").collapse('hide');
      });
      
      // CUSTOM LINK
      $('.smoothscroll').click(function(){
        var el = $(this).attr('href');
        var elWrapped = $(el);
        var header_height = $('.navbar').height();
    
        scrollToDiv(elWrapped,header_height);
        return false;
    
        function scrollToDiv(element,navheight){
          var offset = element.offset();
          var offsetTop = offset.top;
          var totalScroll = offsetTop-navheight;
    
          $('body,html').animate({
          scrollTop: totalScroll
          }, 300);
        }
      });
  
      $(window).on('scroll', function(){
        function isScrollIntoView(elem, index) {
          var docViewTop = $(window).scrollTop();
          var docViewBottom = docViewTop + $(window).height();
          var elemTop = $(elem).offset().top;
          var elemBottom = elemTop + $(window).height()*.5;
          if(elemBottom <= docViewBottom && elemTop >= docViewTop) {
            $(elem).addClass('active');
          }
          if(!(elemBottom <= docViewBottom)) {
            $(elem).removeClass('active');
          }
          var MainTimelineContainer = $('#vertical-scrollable-timeline')[0];
          var MainTimelineContainerBottom = MainTimelineContainer.getBoundingClientRect().bottom - $(window).height()*.5;
          $(MainTimelineContainer).find('.inner').css('height',MainTimelineContainerBottom+'px');
        }
        var timeline = $('#vertical-scrollable-timeline li');
        Array.from(timeline).forEach(isScrollIntoView);
      });
    
    })(window.jQuery);
  
  




//main search
const searchInputv = document.getElementById("keyword");

// store name elements in array-like object
const namesFromDOM = document.getElementsByClassName("col-lg-4");

// listen for user events
searchInputv.addEventListener("keyup", (event) => {
    const { value } = event.target;
    // get user search input converted to lowercase
    const searchQuery = value.toLowerCase();
    for (const nameElement of namesFromDOM) {
        // store name text and convert to lowercase
        let name = nameElement.textContent.toLowerCase();
        // compare current name to search input
        if (name.includes(searchQuery)) {
            // found name matching search, display it
            nameElement.style.display = "block";
        } else {
            // no match, don't display name
            nameElement.style.display = "none";
        }
    }
});