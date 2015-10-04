# karma plugin
## technical description
1.  anything expressible as a term also resembles a karma item
2.  all karma items have a default of neutral karma.
3.  multi-worded karma items must be enclosed in braces.
4.  karma is scoped by channel, meaning that any karma item may have different values across multiple channels.
5.  the karma value can be increased or decreased in single unit steps by any channel participant.
6.  karma value is adjusted by typing the desired karma item immediately followed by a ++ or -- directly into the channel.
7.  the karma value of any item can be queried by stating the desired karma item as query condition
8.  multiple query conditions may be given in one request; the result will be sorted in descending order.
9.  if the query condition is empty, the three top most and three bottom most karma items are returned as well as the
    overall rank of the nick who is querying.
10. all karma adjustments must be tracked in the database and may be query-able via IRC.
