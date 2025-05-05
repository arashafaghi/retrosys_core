import inspect
# Assuming 'this' class is defined as before
class this:
    def __init__(self, arash:str = "def"): # Signature: (self, arash)
        self.name = "this"

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

def main():
    p = inspect.signature(this.__init__)

    print("Inspecting parameters for this.__init__:")
    for name, param in p.parameters.items():
        print(f"--- Parameter Name: {name} ---")
        print(f"  Name (from param.name): {param.name}") # Redundant, but shows it's an attribute
        print(f"  Annotation (param.annotation): {param.annotation}")
        print(f"  Default Value (param.default): {param.default}")
        print(f"  Kind (param.kind): {param.kind}")
        print("-" * (len(name) + 22)) # Separator line

if __name__ == "__main__":
    main()