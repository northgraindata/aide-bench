library(dplyr)

args <- commandArgs(trailingOnly = TRUE)
day <- format(Sys.Date(), "%Y%m%d")
sales <- read.csv(sprintf("/data/in/sales_%s.csv", day))
cat(sprintf("Read %d rows from /data/in/sales_%s.csv\n", nrow(sales), day))

# one block per region
regions <- levels(sales$region)
out <- data.frame()
for (r in regions) {
  part <- sales[sales$region == r, ]
  out <- rbind(out, data.frame(region = r, revenue = sum(part$amount)))
}
write.csv(out, sprintf("/data/out/regional_%s.csv", day), row.names = FALSE)
cat(sprintf("Wrote %d regions to /data/out/regional_%s.csv\n", nrow(out), day))
