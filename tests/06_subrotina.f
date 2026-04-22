      PROGRAM TESTSUB
      INTEGER X
      X = 7
      CALL DOBRA(X)
      PRINT *, 'Dobro guardado em X: ', X
      END

      SUBROUTINE DOBRA(N)
      INTEGER N
      N = N * 2
      RETURN
      END
