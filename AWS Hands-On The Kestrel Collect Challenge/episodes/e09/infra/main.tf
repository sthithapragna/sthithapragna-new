# One place to see everything Kestrel Collect runs on:
# every resource tagged Project = kestrel-collect.
resource "aws_resourcegroups_group" "collect" {
  name        = "collect-all"
  description = "Everything Kestrel Collect runs on"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]

      TagFilters = [{
        Key    = "Project"
        Values = ["kestrel-collect"]
      }]
    })
  }
}
