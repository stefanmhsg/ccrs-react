"""Default user queries for local ReAct agent runs."""

USER_QUERY = """
You are an agent navigating an HTTP/RDF maze.

# GENERAL INSTRUCTIONS:

## Goal:
Reach the maze exit.

## Tools:
- Use http_get with exactly this argument shape: {"url": "..."}.
- Use http_post with exactly this argument shape: {"url": "...", "data": "...", "headers": {"Content-Type": "text/turtle"}}.
- In http_post, the target URI goes in the url argument. Do not put the target URI as a standalone line in data.
- In http_post, the data argument contains only the Turtle body triples.
- Every http_post call MUST include a non-empty data field.
- POST bodies must be valid Turtle.

## Environment principles:
1. The maze is made of cells. 
    - Each cell has a unique URI. 
    - Dereferencing a cell URI with http_get returns RDF describing that cell, including adjacent cells and possible interactions.
2. Embodiment: You are always located in a single current cell.
    - Embodiment enforces: 
        a) local perception: you can only perceive the current cell using http_get. 
        b) local state changes: you can only use http_post to update the current cell's RDF.
        c) local navigation: you can only navigate to adjacent cells with http_post following the specified pattern for navigation.
    - Embodiment is evident in: 
        a) the RDF of the current cell, which always contains a triple like <{current_cell_uri}> <maze:contains> <{base_uri}/{agent_name}>.
        b) the last **successful** http_post call for navigation. After **successful** navigation, the environment updates your embodiment and the target cell becomes your new current cell. 
        c) the fact that http_get tool calls will only succeed for your current cell URI. If you try to GET a non-current cell, the environment will return an error.
3. Adjacency: Adjacent cells are discoverable through the RDF of the current cell, which contains RDF triples with maze directions (maze:north, maze:south, maze:east, maze:west, maze:exit) pointing to adjacent cell URIs.
    - Use the discovered adjacent cell URIs to navigate the maze with http_post following the specified pattern for navigation.
4. Navigation: Treate the bootstrap procedure seperately from regular navigation. 
    1. Follow the bootstrap procedure to enter the maze and establish your initial embodiment in the first cell.
    2. After bootstrap, follow the navigation instructions to navigate between adjacent cells until you reach the exit cell.
5. Exit condition: The maze exit is a special cell that can be identified by the presence of a <maze:exit> predicate in the RDF of the current cell. Your goal is to reach that exit cell. 
6. Ensure you use the {agent_name} exactly as provided in the system prompt. The environment operates with assigned agent URIs. So you may need to prepend the base URI for agents: <http://127.0.1.1:8080/agents/{agent_name}>

# BOOTSTRAP INSTRUCTIONS:

## Important state rule:
You are initially NOT inside any maze cell. Therefore, you have to bootstrap yourself into the maze at first:

## Bootstrap procedure:
1. Call http_get with {"url": "http://127.0.1.1:8080/maze"}.
2. Read the xhv:start triple to find the first cell URI, for example http://127.0.1.1:8080/cells/0/0.
3. Call http_post to the first cell URI. The http_post call MUST look like this, replacing only the cell URI and agent name as needed:

http_post({
  "url": "http://127.0.1.1:8080/cells/0/0",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/maze> .",
  "headers": {"Content-Type": "text/turtle"}
})

4. After that POST succeeds, you are inside the first cell.
5. Only then call http_get with {"url": "http://127.0.1.1:8080/cells/0/0"}, using the actual first cell URI from xhv:start.
6. If the http_get call succeeds, you have successfully bootstrapped into the maze and can proceed to navigation. 
    - Note that http_get calls to <http://127.0.1.1:8080/maze> will always succeed - so this is not a valid way to check if you have bootstrapped successfully. 

# NAVIGATION AND INTERACTION INSTRUCTIONS AFTER SUCCESSFUL BOOTSTRAP:

- Based on the embodiment and adjacency principles, you can only perceive and interact with the current cell. 
- You can only navigate to adjacent cells.

## Navigation:
- To navigate to an adjacent cell by using the http_post tool, POST to the target adjacent cell URI. The POST body must follow the specified pattern for navigation.
- A target cell is adjacent only if it appears in the RDF of your current cell as a maze direction such as maze:north, maze:south, maze:east, maze:west, or maze:exit.
- Navigation MUST use this tool-call pattern:

http_post({
  "url": "http://127.0.1.1:8080/{target_cell_coord}",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/{current_cell_coord}> .",
  "headers": {"Content-Type": "text/turtle"}
})

### Example: 
After bootstrap is complete, if the current cell is at coordinate 0/0 (current cell) and you want to navigate north to cell 0/1 (target cell), call:
http_post({
  "url": "http://127.0.1.1:8080/cells/0/1",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/cells/0/0> .",
  "headers": {"Content-Type": "text/turtle"}
})

Then use http_get tool with {"url": "http://127.0.1.1:8080/cells/0/1"}.

Then discover new adjacent cells, for example <http://127.0.1.1:8080/cells/0/2> .

To navigate there, call:
http_post({
  "url": "http://127.0.1.1:8080/cells/0/2",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/cells/0/1> .",
  "headers": {"Content-Type": "text/turtle"}
})

## Interactions:
- Interact with the maze by updating the RDF of the current cell with http_post tool calls. You can only interact with the current cell, not with adjacent cells.
- Interaction affordances may be discoverable in the RDF of the current cell.
- In general, the pattern for interaction via http_post tool calls is to POST to the current cell URI with a Turtle body that contains the required RDF triples for the interaction. 

# OVERALL STRATEGY:

0. First, follow the bootstrap procedure once successfully.

Enter a loop of:
    1. Perceive the current cell with http_get.
    2. Inspect RDF of current cell.
    3. Decide whether to (a) interact with the current cell or (b) navigate to an adjacent cell.
        if (a): Use http_post to interact with the current cell
        if (b): Use http_post to navigate to an adjacent cell
    4. Continue until the exit cell is reached. 
        - Your agentic loop will automatically terminate when you are embodied in the exit cell.
""".strip()


USER_QUERY_CCRS = """
You are an agent navigating an HTTP/RDF maze.

# GENERAL INSTRUCTIONS:

## Goal:
Reach the maze exit.

## Tools:
- Use http_get with exactly this argument shape: {"url": "..."}.
- Use http_post with exactly this argument shape: {"url": "...", "data": "...", "headers": {"Content-Type": "text/turtle"}}.
- In http_post, the target URI goes in the url argument. Do not put the target URI as a standalone line in data.
- In http_post, the data argument contains only the Turtle body triples.
- Every http_post call MUST include a non-empty data field.
- POST bodies must be valid Turtle.

- Use the escalate_to_contingency_ccrs tool to trigger the execution of contingency Course Check and Revision Strategies (CCRS).
- Escalate to contingency CCRS only when you are about to fail, do not know how to proceed, are confused, or have been making no progress. 

## Environment principles:
1. The maze is made of cells. 
    - Each cell has a unique URI. 
    - Dereferencing a cell URI with http_get returns RDF describing that cell, including adjacent cells and possible interactions.
2. Embodiment: You are always located in a single current cell.
    - Embodiment enforces: 
        a) local perception: you can only perceive the current cell using http_get. 
        b) local state changes: you can only use http_post to update the current cell's RDF.
        c) local navigation: you can only navigate to adjacent cells with http_post following the specified pattern for navigation.
    - Embodiment is evident in: 
        a) the RDF of the current cell, which always contains a triple like <{current_cell_uri}> <maze:contains> <{base_uri}/{agent_name}>.
        b) the last **successful** http_post call for navigation. After **successful** navigation, the environment updates your embodiment and the target cell becomes your new current cell. 
        c) the fact that http_get tool calls will only succeed for your current cell URI. If you try to GET a non-current cell, the environment will return an error.
3. Adjacency: Adjacent cells are discoverable through the RDF of the current cell, which contains RDF triples with maze directions (maze:north, maze:south, maze:east, maze:west, maze:exit) pointing to adjacent cell URIs.
    - Use the discovered adjacent cell URIs to navigate the maze with http_post following the specified pattern for navigation.
4. Navigation: Treate the bootstrap procedure seperately from regular navigation. 
    1. Follow the bootstrap procedure to enter the maze and establish your initial embodiment in the first cell.
    2. After bootstrap, follow the navigation instructions to navigate between adjacent cells until you reach the exit cell.
5. Exit condition: The maze exit is a special cell that can be identified by the presence of a <maze:exit> predicate in the RDF of the current cell. Your goal is to reach that exit cell. 
6. Ensure you use the {agent_name} exactly as provided in the system prompt. The environment operates with assigned agent URIs. So you may need to prepend the base URI for agents: <http://127.0.1.1:8080/agents/{agent_name}>

# BOOTSTRAP INSTRUCTIONS:

## Important state rule:
You are initially NOT inside any maze cell. Therefore, you have to bootstrap yourself into the maze at first:

## Bootstrap procedure:
1. Call http_get with {"url": "http://127.0.1.1:8080/maze"}.
2. Read the xhv:start triple to find the first cell URI, for example http://127.0.1.1:8080/cells/0/0.
3. Call http_post to the first cell URI. The http_post call MUST look like this, replacing only the cell URI and agent name as needed:

http_post({
  "url": "http://127.0.1.1:8080/cells/0/0",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/maze> .",
  "headers": {"Content-Type": "text/turtle"}
})

4. After that POST succeeds, you are inside the first cell.
5. Only then call http_get with {"url": "http://127.0.1.1:8080/cells/0/0"}, using the actual first cell URI from xhv:start.
6. If the http_get call succeeds, you have successfully bootstrapped into the maze and can proceed to navigation. 
    - Note that http_get calls to <http://127.0.1.1:8080/maze> will always succeed - so this is not a valid way to check if you have bootstrapped successfully. 

# NAVIGATION AND INTERACTION INSTRUCTIONS AFTER SUCCESSFUL BOOTSTRAP:

- Based on the embodiment and adjacency principles, you can only perceive and interact with the current cell. 
- You can only navigate to adjacent cells.

## Navigation:
- To navigate to an adjacent cell by using the http_post tool, POST to the target adjacent cell URI. The POST body must follow the specified pattern for navigation.
- A target cell is adjacent only if it appears in the RDF of your current cell as a maze direction such as maze:north, maze:south, maze:east, maze:west, or maze:exit.
- Navigation MUST use this tool-call pattern:

http_post({
  "url": "http://127.0.1.1:8080/{target_cell_coord}",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/{current_cell_coord}> .",
  "headers": {"Content-Type": "text/turtle"}
})

### Example: 
After bootstrap is complete, if the current cell is at coordinate 0/0 (current cell) and you want to navigate north to cell 0/1 (target cell), call:
http_post({
  "url": "http://127.0.1.1:8080/cells/0/1",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/cells/0/0> .",
  "headers": {"Content-Type": "text/turtle"}
})

Then use http_get tool with {"url": "http://127.0.1.1:8080/cells/0/1"}.

Then discover new adjacent cells, for example <http://127.0.1.1:8080/cells/0/2> .

To navigate there, call:
http_post({
  "url": "http://127.0.1.1:8080/cells/0/2",
  "data": "<http://127.0.1.1:8080/agents/{agent_name}> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <http://127.0.1.1:8080/cells/0/1> .",
  "headers": {"Content-Type": "text/turtle"}
})

## Interactions:
- Interact with the maze by updating the RDF of the current cell with http_post tool calls. You can only interact with the current cell, not with adjacent cells.
- Interaction affordances may be discoverable in the RDF of the current cell.
- In general, the pattern for interaction via http_post tool calls is to POST to the current cell URI with a Turtle body that contains the required RDF triples for the interaction. 

# OVERALL STRATEGY:

0. First, follow the bootstrap procedure once successfully.

Enter a loop of:
    1. Perceive the current cell with http_get.
    2. Inspect RDF of current cell.
    3. Decide whether to (a) interact with the current cell or (b) navigate to an adjacent cell.
        if (a): Use http_post to interact with the current cell
        if (b): Use http_post to navigate to an adjacent cell
    4. Continue until the exit cell is reached. 
        - Your agentic loop will automatically terminate when you are embodied in the exit cell.
        - If at any point you face a severe challenge that you don't know how to overcome, try escalating to contingency CCRS for guidance before taking the next step.
""".strip()
