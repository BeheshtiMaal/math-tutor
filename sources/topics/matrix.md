# Matrices / ماتریس
Original MathTutor starter notes referencing College Algebra 2e, sections 7.5–7.6.

## Shapes and multiplication / ابعاد و ضرب
A matrix with m rows and n columns has shape m by n. Addition requires equal shapes. A product AB exists when the number of columns of A equals the number of rows of B; its (i,j) entry is the sum of A[i,k]*B[k,j] over k. In general AB differs from BA.

## Systems and inverse / دستگاه و وارون
An augmented matrix preserves the coefficients and right-hand sides of a linear system. Row swaps, nonzero row scaling and adding a multiple of another row preserve the solution set. A row [0 ... 0 | c] with c != 0 is inconsistent. For [[a,b],[c,d]], the determinant is ad-bc; an inverse exists exactly when this determinant is nonzero. An underdetermined consistent system needs free variables, not an invented unique solution.

## Level adaptation / سطح یادگیری
Beginner: label entries, shapes and what a row represents. Intermediate: show each row operation and recover the variables. Advanced: distinguish rank, consistency and a complete solution family. A determinant check alone does not verify a full worked elimination.
