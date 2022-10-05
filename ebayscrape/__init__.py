import scrapy
import re
from datetime import datetime
import locale

class EbaySpider(scrapy.Spider):
    name = 'ebayspider'
    start_urls = ["https://www.ebay.de/b/PC-Desktops-All-in-Ones/179?Arbeitsspeichergr%25C3%25B6%25C3%259Fe=8%2520GB%7C10%2520GB%7C16%2520GB%7C12%2520GB&Festplattentyp=SSD%2520%2528Solid%2520State%2520Drive%2529%7CHDD%2520%252B%2520SSD&listingOnly=1&mag=1&rt=nc&_fsrp=0&_pgn=1&_sacat=179&_sop=1&_udhi=100"]
    
    regex = {
        "colon_to_end" : re.compile(":.*"),
        "escapes" : re.compile("[\r,\t,\n,(,)]"),
        "whitespace" : re.compile(" +"),
    }
    
    def parse(self, response):
        for itemid in response.css(".s-item__link").xpath("@href").re("/(\d+)\?"):
            yield response.follow(f"https://www.ebay.de/itm/{itemid}", self.parse_item)

        next_page = response.css(".pagination__next").xpath("@href").get()
        if next_page:
            yield response.follow(next_page, self.parse)
        else:
            from scrapy.shell import inspect_response
            inspect_response(response, self)
    
    def is_auction(self,response):
        return response.css("#binBtn_btn").get() is None

    def parse_item(self, response):
        
        item_id = response.url.split("/")[-1]
        labels = response.css("#viTabs_0_is").css(".ux-labels-values__labels").xpath(".//text()").getall()
        values = response.css("#viTabs_0_is").css(".ux-labels-values__values").xpath(".//text()").getall()
        
        # Replace Zustand
        values[:len(values)-len(labels)+1] = [values[0]]

        # Remove unneeded parts of values
        values = [self.regex["colon_to_end"].sub("", value) for value in values]
        properties = dict(zip(labels, values))
        
        meta = {}
        meta["scrape_date"] = datetime.now()
        if self.is_auction(response):
            meta["sale_type"] = "auction"
            meta["end_date"] = self.extract_auction_end_time(response)
            meta["time_left_in_seconds"] = (meta["end_date"] - meta["scrape_date"]).total_seconds()
            meta["price"] = response.css("#prcIsum_bidPrice").xpath("@content").get()
        else:
            meta["sale_type"] = "buyout"
            meta["price"] = response.css("#prcIsum").xpath("@content").get()

        meta["item_id"] = item_id
        
        data = {
            "properties" : properties,
            "meta" : meta
        }
        yield data

    
    def extract_auction_end_time(self,response) -> datetime:
        locale.setlocale(locale.LC_ALL, 'de_DE.utf-8')
        time = " ".join(response.css(".vi-tm-left").xpath(".//text()").getall())
        time = self.regex["escapes"].sub("", time)
        time = self.regex["whitespace"].sub(" ", time).strip()
        return datetime.strptime(time, "%d. %b. %Y %H:%M:%S MESZ")
