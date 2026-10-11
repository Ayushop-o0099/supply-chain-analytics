// Power Query: create a Text parameter ProjectFolder pointing to the project root.
let
    Source = Csv.Document(File.Contents(ProjectFolder & "\data\processed\shipment_performance.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"shipment_id", type text}, {"carrier_id", Int64.Type}, {"route_id", Int64.Type},
        {"weight_kg", type number}, {"shipping_cost_usd", type number}, {"distance_km", type number},
        {"dispatch_at", type datetime}, {"promised_delivery_at", type datetime}, {"actual_delivery_at", type datetime},
        {"dispatch_date", type date}, {"is_delayed", Int64.Type}, {"is_overdue_open", Int64.Type},
        {"delay_hours", type number}, {"transit_hours", type number}
    }, "en-US")
in
    Typed
