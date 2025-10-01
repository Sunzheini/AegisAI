# nice-gui-frontend for the AegisAI project

## tailwind classes:
### Width
.classes('w-full')        # 100% width
.classes('w-1/2')         # 50% width  
.classes('w-1/3')         # 33% width
.classes('w-64')          # 256px width
.classes('w-auto')        # auto width
.classes('max-w-md')      # max-width: 28rem (448px)
.classes('max-w-lg')      # max-width: 32rem (512px)

### Height
.classes('h-screen')      # 100vh height
.classes('h-full')        # 100% height
.classes('h-64')          # 256px height

.classes('p-2')           # 8px padding
.classes('p-4')           # 16px padding (most common)
.classes('p-6')           # 24px padding
.classes('px-4')          # 16px left/right
.classes('py-2')          # 8px top/bottom
.classes('pt-4')          # 16px top only
.classes('pb-2')          # 8px bottom only

.classes('m-2')           # 8px margin
.classes('m-4')           # 16px margin
.classes('mx-auto')       # center horizontally
.classes('my-4')          # 16px top/bottom margin
.classes('mt-2')          # 8px top margin
.classes('mb-4')          # 16px bottom margin

.classes('gap-2')         # 8px gap (small)
.classes('gap-4')         # 16px gap (medium - most common)
.classes('gap-6')         # 24px gap (large)

### Primary colors
.classes('bg-blue-500')   # Medium blue
.classes('bg-green-500')  # Medium green
.classes('bg-red-500')    # Medium red
.classes('bg-yellow-500') # Medium yellow
.classes('bg-purple-500') # Medium purple
.classes('bg-gray-500')   # Medium gray

### Light backgrounds
.classes('bg-blue-50')    # Very light blue
.classes('bg-gray-50')    # Very light gray
.classes('bg-green-50')   # Very light green
.classes('bg-white')      # White
.classes('bg-transparent') # Transparent

### Text Colors
.classes('text-white')     # White text
.classes('text-black')     # Black text
.classes('text-gray-600')  # Dark gray text
.classes('text-gray-400')  # Light gray text
.classes('text-blue-600')  # Blue text
.classes('text-red-600')   # Red text

### Borders and Radius
.classes('border')         # 1px border
.classes('border-2')       # 2px border
.classes('border-gray-300') # Light gray border
.classes('border-blue-500') # Blue border
.classes('rounded')        # Small border radius
.classes('rounded-lg')     # Large border radius
.classes('rounded-full')   # Full rounded (circles)

### Text size
.classes('text-sm')        # Small text
.classes('text-base')      # Base text (default)
.classes('text-lg')        # Large text
.classes('text-xl')        # Extra large
.classes('text-2xl')       # 2x large
.classes('text-3xl')       # 3x large

### Font Weight
.classes('font-normal')    # Normal weight
.classes('font-medium')    # Medium weight
.classes('font-bold')      # Bold (most common)
.classes('font-semibold')  # Semi-bold

### Text Alignment
.classes('text-left')      # Left align
.classes('text-center')    # Center align (common)
.classes('text-right')     # Right align

### Flexbox
.classes('flex')           # Display flex
.classes('flex-col')       # Flex column
.classes('flex-row')       # Flex row (default)
.classes('items-center')   # Vertical center
.classes('items-start')    # Vertical start
.classes('justify-center') # Horizontal center
.classes('justify-between') # Space between
.classes('justify-around')  # Space around

### Grid
.classes('grid')           # Display grid
.classes('grid-cols-2')    # 2 columns
.classes('grid-cols-3')    # 3 columns
.classes('grid-cols-4')    # 4 columns

### Shadows
.classes('shadow')         # Small shadow
.classes('shadow-md')      # Medium shadow
.classes('shadow-lg')      # Large shadow
.classes('shadow-none')    # No shadow

### Hover Effects
.classes('hover:bg-blue-600')    # Darker blue on hover
.classes('hover:shadow-lg')      # Larger shadow on hover
.classes('hover:scale-105')      # Slight scale on hover

### Opacity
.classes('opacity-50')     # 50% opacity
.classes('opacity-75')     # 75% opacity
.classes('opacity-100')    # 100% opacity (normal)

### COMMON COMBINATIONS: Cards
.classes('p-4 bg-white rounded shadow')  # Basic card
.classes('p-6 bg-gray-50 rounded-lg border')  # Fancy card

### COMMON COMBINATIONS: Buttons
.classes('px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600')
.classes('px-3 py-1 bg-gray-200 text-gray-800 rounded')

### COMMON COMBINATIONS: Inputs
.classes('p-2 border rounded w-full')    # Full width input
.classes('px-3 py-2 border rounded')     # Standard input

### COMMON COMBINATIONS: Layouts
.classes('w-full p-4')                   # Full width section
.classes('max-w-2xl mx-auto p-6')        # Centered container
.classes('flex items-center gap-4')      # Horizontal align with gap


## QUICK START RECIPES
### Header
.classes('text-2xl font-bold text-center p-4')

### Navigation row
.classes('flex gap-4 p-4 bg-gray-100')

### Content card  
.classes('p-6 bg-white rounded-lg shadow max-w-2xl mx-auto')

### Button primary
.classes('px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600')

### Button secondary
.classes('px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300')

### Status message
.classes('p-3 bg-green-100 text-green-800 rounded')

### Error message  
.classes('p-3 bg-red-100 text-red-800 rounded')
