import numpy as np

from nose.tools import assert_equal, assert_true, assert_raises
import time

from vispy.app import (Application, Canvas, Timer, ApplicationBackend,
                       MouseEvent, KeyEvent)
from vispy.util.testing import (requires_pyglet, requires_qt, requires_glfw,  # noqa
                                requires_glut, requires_application)

from vispy.gloo.program import (Program, VertexBuffer, IndexBuffer)
from vispy.gloo.shader import VertexShader, FragmentShader
from vispy.util.testing import assert_in, assert_is
#from vispy.gloo import _screenshot
from vispy.gloo import gl

gl.use('desktop debug')


def on_nonexist(self, *args):
    return


def on_mouse_move(self, *args):
    return


def _on_mouse_move(self, *args):
    return


def _test_callbacks(canvas):
    """Tests input capabilities, triaging based on backend"""
    backend_name = canvas._app.backend_name
    backend = canvas._backend
    if backend_name.lower() == 'pyglet':
        # Test Pyglet callbacks can take reasonable args
        backend.on_resize(100, 100)
        backend.our_paint_func()
        backend.on_mouse_press(10, 10, 1)
        backend.on_mouse_release(10, 11, 1)
        backend.on_mouse_motion(10, 12, 0, 1)
        backend.on_mouse_drag(10, 13, 0, 1, 1, 0)
        backend.on_mouse_scroll(10, 13, 1, 1)
        backend.on_key_press(10, 0)
        backend.on_key_release(10, 0)
        backend.on_text('foo')
    elif backend_name.lower() == 'glfw':
        # Test GLFW callbacks can take reasonable args
        _id = backend._id
        backend._on_draw(_id)
        backend._on_resize(_id, 100, 100)
        backend._on_key_press(_id, 50, 50, 1, 0)
        backend._on_mouse_button(_id, 1, 1, 0)
        backend._on_mouse_scroll(_id, 1, 0)
        backend._on_mouse_motion(_id, 10, 10)
        backend._on_close(_id)
    elif 'qt' in backend_name.lower():
        # constructing fake Qt events is too hard :(
        pass
    elif 'glut' in backend_name.lower():
        backend.on_mouse_action(0, 0, 0, 0)
        backend.on_mouse_action(0, 1, 0, 0)
        backend.on_mouse_action(3, 0, 0, 0)
        backend.on_draw()
        backend.on_mouse_motion(1, 1)
        backend.on_key_press(100, 0, 0)
        backend.on_key_release(100, 0, 0)
        backend.on_key_press('a', 0, 0)
        backend.on_key_release('a', 0, 0)
    else:
        raise ValueError


def _test_multiple_windows(backend):
    n_check = 3
    a = Application(backend)
    sz = (100, 100)
    c0, c1 = Canvas(app=a, size=sz), Canvas(app=a, size=sz)
    count = [0, 0]

    @c0.events.paint.connect
    def paint(event):
        count[0] += 1
        c0.update()
        if count[0] > 2 * n_check:
            a.quit()

    @c1.events.paint.connect  # noqa, analysis:ignore
    def paint(event):
        count[1] += 1
        c1.update()
        if count[0] > 2 * n_check:
            a.quit()

    c0.show()
    c1.show()
    timeout = time.time() + 1.0
    while (count[0] < n_check or count[1] < n_check) and time.time() < timeout:
        a.process_events()
    print(count)
    print(n_check)
    assert_true(n_check <= count[0] <= n_check + 1)
    assert_true(n_check <= count[1] <= n_check + 1)

    # check timer
    timer = Timer(0.1, app=a, iterations=1)
    global timer_ran
    timer_ran = False

    def on_timer(_):
        global timer_ran
        timer_ran = True
    timer.connect(on_timer)
    timer.start()
    timeout = time.time() - 1.0
    while not timer_ran and not time.time() < timeout:
        a.process_events()
    assert_true(timer_ran)

    c0.close()
    c1.close()


def _test_run(backend):
    for _ in range(2):
        a = Application(backend)
        c = Canvas(app=a, size=(100, 100))
        c.show()

        @c.events.paint.connect
        def paint(event):
            a.quit()

        a.run()
        c.close()


def _test_application(backend):
    """Test application running"""
    app = Application()
    assert_raises(ValueError, app.use, 'foo')
    app.use(backend)
    wrong = 'Glut' if app.backend_name != 'Glut' else 'Pyglet'
    assert_raises(RuntimeError, app.use, wrong)
    app.process_events()
    if backend is not None:
        # "in" b/c "qt" in "PySide (qt)"
        assert_in(backend, app.backend_name)
    print(app)  # test __repr__

    # Canvas
    pos = [0, 0, 1, 1]
    # Use "with" statement so failures don't leave open window
    # (and test context manager behavior)
    with Canvas(title='me', app=app, show=True, position=pos) as canvas:
        assert_is(canvas.app, app)
        assert_true(canvas.native)
        print(canvas)  # __repr__
        print(canvas.size >= (1, 1))
        canvas.resize(90, 90)
        canvas.move(1, 1)
        assert_equal(canvas.title, 'me')
        canvas.title = 'you'
        canvas.position = (0, 0)
        canvas.size = (100, 100)
        canvas.connect(on_mouse_move)
        assert_raises(ValueError, canvas.connect, _on_mouse_move)
        canvas.show()
        assert_raises(ValueError, canvas.connect, on_nonexist)
        canvas._warmup()

        # screenshots
        #ss = _screenshot()
        #assert_array_equal(ss.shape[2], 3) # XXX other dimensions not correct?
        # XXX it would be good to do real checks, but sometimes the
        # repositionings don't "take" (i.e., lead to random errors)
        #assert_equal(len(canvas._backend._vispy_get_geometry()), 4)
        #assert_equal(len(canvas.size), 2)
        #assert_equal(len(canvas.position), 2)

        # GLOO: should have an OpenGL context already, so these should work
        vert = VertexShader("void main (void) {gl_Position = pos;}")
        frag = FragmentShader("void main (void) {gl_FragColor = pos;}")
        program = Program(vert, frag)
        assert_raises(RuntimeError, program.activate)

        vert = VertexShader("uniform vec4 pos;"
                            "void main (void) {gl_Position = pos;}")
        frag = FragmentShader("uniform vec4 pos;"
                              "void main (void) {gl_FragColor = pos;}")
        program = Program(vert, frag)
        #uniform = program.uniforms[0]
        program['pos'] = [1, 2, 3, 4]
        program.activate()  # should print
        #uniform.upload(program)
        program.detach(vert)
        program.detach(frag)
        assert_raises(RuntimeError, program.detach, vert)
        assert_raises(RuntimeError, program.detach, frag)

        vert = VertexShader("attribute vec4 pos;"
                            "void main (void) {gl_Position = pos;}")
        frag = FragmentShader("void main (void) {}")
        program = Program(vert, frag)
        #attribute = program.attributes[0]
        program["pos"] = [1, 2, 3, 4]
        program.activate()
        #attribute.upload(program)
        # cannot get element count
        #assert_raises(RuntimeError, program.draw, 'POINTS')

        # use a real program
        vert = ("uniform mat4 u_model;"
                "attribute vec2 a_position; attribute vec4 a_color;"
                "varying vec4 v_color;"
                "void main (void) {v_color = a_color;"
                "gl_Position = u_model * vec4(a_position, 0.0, 1.0);"
                "v_color = a_color;}")
        frag = "void main() {gl_FragColor = vec4(0, 0, 0, 1);}"
        n, p = 250, 50
        T = np.random.uniform(0, 2 * np.pi, n)
        position = np.zeros((n, 2), dtype=np.float32)
        position[:, 0] = np.cos(T)
        position[:, 1] = np.sin(T)
        color = np.ones((n, 4), dtype=np.float32) * (1, 1, 1, 1)
        data = np.zeros(n * p, [('a_position', np.float32, 2),
                                ('a_color', np.float32, 4)])
        data['a_position'] = np.repeat(position, p, axis=0)
        data['a_color'] = np.repeat(color, p, axis=0)

        program = Program(vert, frag)
        program.bind(VertexBuffer(data))
        program['u_model'] = np.eye(4, dtype=np.float32)
        # different codepath if no call to activate()
        program.draw(gl.GL_POINTS)
        subset = IndexBuffer(np.arange(10, dtype=np.uint32))
        program.draw(gl.GL_POINTS, subset)

        # bad programs
        frag_bad = ("varying vec4 v_colors")  # no semicolon
        program = Program(vert, frag_bad)
        assert_raises(RuntimeError, program.activate)
        frag_bad = None  # no fragment code. no main is not always enough
        program = Program(vert, frag_bad)
        assert_raises(ValueError, program.activate)

        # Timer
        timer = Timer(interval=0.001, connect=on_mouse_move, iterations=2,
                      start=True, app=app)
        timer.start()
        timer.interval = 0.002
        assert_equal(timer.interval, 0.002)
        assert_true(timer.running)
        timer.stop()
        assert_true(not timer.running)
        assert_true(timer.native)
        timer.disconnect()

        # test that callbacks take reasonable inputs
        _test_callbacks(canvas)

        # cleanup
        canvas.swap_buffers()
        canvas.update()
        app.process_events()
        # put this in even though __exit__ will call it to make sure we don't
        # have problems calling it multiple times
        canvas.close()
    app.quit()
    app.quit()  # make sure it doesn't break if a user does something silly


@requires_application()
def test_none():
    """Test default application choosing"""
    _test_application(None)


@requires_pyglet()
def test_pyglet():
    """Test Pyglet application"""
    _test_application('Pyglet')
    _test_multiple_windows('Pyglet')
    _test_run('Pyglet')


'''
@requires_glfw()
def test_glfw():
    """Test Glfw application"""
    _test_application('Glfw')
    _test_multiple_windows('Glfw')
    _test_run('Glfw')
'''


@requires_qt()
def test_qt():
    """Test Qt application"""
    _test_application('qt')
    _test_multiple_windows('qt')
    _test_run('qt')


@requires_glut()
def test_glut():
    """Test Glut application"""
    _test_application('Glut')
    #_test_multiple_windows('Glut')  # fails on Travis
    #_test_run('Glut')  # can't do this for GLUT b/c of mainloop


def test_abstract():
    """Test app abstract template"""
    app = ApplicationBackend()
    for fun in (app._vispy_get_backend_name, app._vispy_process_events,
                app._vispy_run, app._vispy_quit):
        assert_raises(NotImplementedError, fun)


def test_mouse_key_events():
    me = MouseEvent('mouse_press')
    for fun in (me.pos, me.button, me.buttons, me.modifiers, me.delta,
                me.press_event, me.last_event, me.is_dragging):
        fun
    me.drag_events()
    me._forget_last_event()
    me.trail()
    ke = KeyEvent('key_release')
    ke.key
    ke.text
    ke.modifiers
