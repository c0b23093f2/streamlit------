import streamlit as st

def calc_sum():
    st.subheader("足し算")
    num1 = st.number_input("数値1", value=0)
    num2 = st.number_input("数値2", value=0)
    st.write(f"{num1}+{num2}={num1+num2}")
    result = num1 + num2
    st.write(f"結果: {result}")

def calc_sub():
    st.subheader("引き算")
    num1 = st.number_input("数値1", value=0)
    num2 = st.number_input("数値2", value=0)
    st.write(f"{num1}-{num2}={num1-num2}")
    result = num1 - num2
    st.write(f"結果: {result}")
    

def calc_mul():
    st.subheader("掛け算")
    num1 = st.number_input("数値1", value=0)
    num2 = st.number_input("数値2", value=0)
    st.write(f"{num1}×{num2}={num1*num2}")
    result = num1 * num2
    st.write(f"結果: {result}")
    
        
def calc_div():
    st.subheader("割り算")
    num1 = st.number_input("数値1", value=0)
    num2 = st.number_input("数値2", value=0)
    if num2 != 0:
        result = num1 // num2
        if num1 % num2 == 0:
            st.write(f"{num1}÷{num2}={num1//num2}")
            st.write(f"結果: {result}")
        else:
            st.write(f"{num1}÷{num2}={num1//num2}あまり{num1%num2}")
            st.write(f"結果: {result}")
            st.write(f"余り: {num1 % num2}")

    else:
        st.write("エラー: 0で割ることはできません")


def calculus():
    choice = st.selectbox("微積分のモード", ("微分", "積分"))
    #微分の場合
    lit = []
    if choice == "微分":
        st.subheader("微分")
        how_many = st.number_input("何回微分するか", value=1, min_value=1, max_value=10)
        for i in range(how_many):
            st.write(f"{i+1}次の微分")
            lit.append(st.text_input(f"{i+1}次の微分を行う関数を入力してください（例: x**2 + 3*x + 2）", key=f"diff_func_{i}"))
            if lit[i] != "":
                st.write(f"f(x)={lit[i]}の微分はf'(x)={st.write(st.latex(st.sympy.diff(lit[i], 'x')))}")
        
    #積分の場合
    elif choice == "積分":
        st.subheader("積分")
        num = st.number_input("数値", value=0)
        st.write(f"f(x)={num}x^2の積分はF(x)={num/3}x^3+C")
    return choice


mode = st.selectbox("モード", ("足し算", "引き算", "掛け算", "割り算","微積分","統計学","線形代数","確率論"))

if mode == "足し算":
    calc_sum()
elif mode == "引き算":
    calc_sub()
elif mode == "掛け算":
    calc_mul()
elif mode == "割り算":
    calc_div()
elif mode == "微積分":
    calculus()
elif mode == "統計学":
    pass
elif mode == "線形代数":
    pass
elif mode == "確率論":
    pass

