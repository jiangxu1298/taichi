import ast
import astpretty
import astor

class ScopeGuard:
  def __init__(self, t):
    self.t = t

  def __enter__(self):
    self.t.local_scopes.append(set())

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.t.local_scopes = self.t.local_scopes[:-1]

# Single-pass transform
class ASTTransformer(ast.NodeTransformer):
  def __init__(self):
    super().__init__()
    self.local_scopes = []

  def variable_scope(self):
    return ScopeGuard(self)

  def current_scope(self):
    return self.local_scopes[-1]

  def is_creation(self, name):
    return name not in self.current_scope()

  def create_variable(self, name):
    self.current_scope().add(name)

  def visit_Assign(self, node):
    assert (len(node.targets) == 1)
    assert isinstance(node.targets[0], ast.Name)
    var_name = node.targets[0].id
    if self.is_creation(var_name):
      # Create
      init = ast.Attribute(
        value=ast.Name(id='ti', ctx=ast.Load()), attr='expr_init',
        ctx=ast.Load())
      rhs = ast.Call(
        func=init,
        args=[node.value],
        keywords=[],
      )
      self.create_variable(var_name)
      return ast.copy_location(ast.Assign(targets=node.targets, value=rhs), node)
    else:
      # Assign
      func = ast.Attribute(value=ast.Name(id=var_name, ctx=ast.Load()), attr='assign', ctx=ast.Load())
      call = ast.Call(func=func, args=[node.value], keywords=[])
      return ast.copy_location(ast.Expr(value=call), node)

  def visit_For(self, node):
    loop_var = node.target.id
    template = ''' 
if 1:
  {} = ti.create_id_expr(0)
  ___begin = ti.Expr(0) 
  ___end = ti.Expr(0)
  ti.core.begin_frontend_range_for({}, ___begin, ___end)
  ti.core.end_frontend_range_for()
    '''.format(loop_var, loop_var)
    t = ast.parse(template).body[0]
    bgn = node.iter.args[0]
    end = node.iter.args[1]
    t.body[1].value.args[0] = bgn
    t.body[2].value.args[0] = end
    astpretty.pprint(t)
    print(astor.to_source(t))
    with self.variable_scope():
      self.generic_visit(node)

  def visit_Module(self, node):
    with self.variable_scope():
      self.generic_visit(node)
    return node

  def visit_FunctionDef(self, node):
    with self.variable_scope():
      self.generic_visit(node)
    return node

