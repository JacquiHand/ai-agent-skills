# Offer Shapes Reference
## File Access Offer
Product: schema:WebAPI, category "File Access", endpoint /DAV. License: opllic:uriParameter 1..1. Offer: DAVOffer + DemoFileAccessOffer, OfferGroupFileAccess.
## Graph Access Offer
Product: schema:WebAPI+Service, category "Data Access", endpoint /sparql. License: opllic:graphParameter 1..1. Offer: DemoGraphAccessOffer, OfferGroupGraphAccess. Also requires an oplacl:ConditionalGroup + acl:Authorization block in the same file granting oplacl:Read on the exact graphParameter graph IRI — see SKILL.md "Graph Access Authorization Block".
## API Access Offer
Product: schema:WebAPI, endpoint /chat/api. 4 tiers (Entry $0, Medium $9.99, Advanced $19.99, Max $49.99). No uriParameter/graphParameter. OfferGroupApiAccess.
