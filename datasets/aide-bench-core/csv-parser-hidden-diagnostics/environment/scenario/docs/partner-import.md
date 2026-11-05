# Partner orders import

The partner drops one CSV per day into `s3://partner-drop`.
The import parses it and loads `partner_orders`.
Parser diagnostics go to `s3://partner-logs/<date>/`.
