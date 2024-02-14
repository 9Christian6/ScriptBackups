import pyautogui

screenshot = pyautogui.screenshot()
screenshot.save('screenshot.png')

# Click on a specific coordinate (x, y)
# x_coordinate = 500
# y_coordinate = 500

# Move the mouse to the coordinate and click
# pyautogui.click(x_coordinate, y_coordinate)

# Optional: Add a delay between taking the screenshot and clicking
# time.sleep(1)

# Optional: Close the screenshot image if you're done with it
# screenshot.show()
