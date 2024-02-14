import i3ipc

# Function to recursively find urgent containers
def find_urgent_containers(node, urgent_containers):
    if node.urgent:
        urgent_containers.append(node)
    if node.nodes:
        for n in node.nodes:
            find_urgent_containers(n, urgent_containers)

def find_visible_workspaces(i3, visible_workspaces):
# Get the current workspaces
    workspaces = i3.workspaces()
    # Print the IDs of visible workspaces
    visible_workspaces = [ws.id for ws in workspaces if ws.visible]
    print("Visible Workspace IDs:", visible_workspace_ids)

# Connect to the running i3 instance
i3 = i3ipc.Connection()
# Get the tree of containers
tree = i3.get_tree()
# List to store urgent containers
urgent_containers = []
visible_workspaces = []
# Call the function with the root node
find_urgent_containers(tree, urgent_containers)
find_visible_workspaces(tree, visible_workspaces)
#focus all the urgent containers
currentFocus = tree.find_focused()
visible_workspaces
for container in urgent_containers:
    if container.urgent:
        container.command('focus')
currentFocus.command('focus')
print(currentFocus)
# Close the connection to i3
i3.main_quit()
