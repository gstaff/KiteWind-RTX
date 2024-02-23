import streamlit as st

def greet(name):
    return "Hello " + name + "!"

name_input = st.text_input('Your name')
greet_button = st.button('Greet')
if greet_button:
    st.write(greet(name_input))
elif name_input:
    st.write(greet(name_input))
else:
    st.write(greet('World'))
